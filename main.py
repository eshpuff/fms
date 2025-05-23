import subprocess
import threading
import time
import psutil
import os
import sys

# pede ao usuário as informações do programa 
def askUserData(quota_restante):
    print(f"\nQuota de CPU restante: {quota_restante:.2f} segundos")
    binaryPath = input("Caminho do programa (ex: C:\\Windows\\System32\\notepad.exe): ").strip() #solicita caminho para o binário

    if binaryPath.lower() == "sair": #para sair do programa manualmente
        return None

    try:
        timeout = float(input("Tempo limite de execução (em segundos): "))
        memoryLimit = float(input("Limite máximo de memória (em MB): ")) * 1024 * 1024 # converte mb para bytes
    except ValueError:
        print("Entrada inválida")
        return None

    # retorna um dicionario com dados
    return {
        "binaryPath": binaryPath,
        "binaryName": os.path.basename(binaryPath), # nome do binário
        "timeout": timeout,
        "limiteMemoria": memoryLimit
    }

# busca processos pelo nome
def findProcessByName(name):
    matching = []

    # itera sobre todos os processos
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == name.lower(): #compara os nomes
                matching.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue #ignora os processos que já morreram
    return matching


# seleciona o processo ativo mais recente
def selectActiveProcess(binaryName):
    processes = findProcessByName(binaryName) # procura pelo nome do binário
    if not processes:
        return None
    
    #retorna o último da lista
    process = sorted(processes, key=lambda p: p.create_time())[-1]
    return process

#mata o pai e os filhos 
def killAll(proc):
    try:
        children = proc.children(recursive=True)
        for child in children: # mata os filhos com recursão
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        proc.kill() # e então mata o pai
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

# monitora o processo
def MonitorProcess(data, quota_restante, prePago, saldo, tariffPerSecond, saldo_lock):
    try:
        cmd = f'cmd /c start "" "{data["binaryPath"]}"' # executa o binairo via cmd
        print("[INFO] Executando:")
        subprocess.Popen(cmd, shell=True)

        # da um tempo para ele iniciar
        time.sleep(3)
        process = selectActiveProcess(data['binaryName']) #locALiza o processo 

        if not process:
            print("[ERRO] Processo não encontrado após iniciar.")
            return 0, False

        print(f"[INFO] Processo detectado: PID={process.pid} ({process.name()})")

        #valiavéis de monitoramento
        startTime = time.time()
        max_memory = 0
        last_user_cpu = 0
        last_system_cpu = 0
        reason = "finalizado_normalmente"

        while True:
            elapsedTime = time.time() - startTime

            if not process.is_running():
                break

            try: #uso da cpu (usuário e sistema)
                cpu_times = process.cpu_times()
                cpu_user = cpu_times.user
                cpu_system = cpu_times.system
                cpu_total = cpu_user + cpu_system

                memory_usage = process.memory_info().rss # uso de memória
                if memory_usage > max_memory:
                    max_memory = memory_usage

                print(f'[MONITOR | PID={process.pid}] CPU: {cpu_total:.2f}s | MEM: {memory_usage / (1024 * 1024):.2f}MB | Tempo: {elapsedTime:.2f}s') #atualizações

                #verificação de limites
                if cpu_total >= quota_restante: 
                    print(f"[ALERTA | PID={process.pid}] Quota de CPU excedida. Encerrando processo.")
                    killAll(process)
                    reason = "quota_excedida"
                    break

                if memory_usage >= data['limiteMemoria']:
                    print(f"[ALERTA | PID={process.pid}] Limite de memória excedido.")

                if elapsedTime >= data['timeout']:
                    print(f"[INFO | PID={process.pid}] Tempo limite atingido.")
                    reason = "tempo_excedido"
                    killAll(process)
                    break

                last_user_cpu = cpu_user
                last_system_cpu = cpu_system

                time.sleep(1) #delay de atualização

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"[INFO | PID={process.pid}] Processo inacessível ou encerrado.")
                break

        # calculo final
        cpu_total = last_user_cpu + last_system_cpu
        executionCost = round(cpu_total * tariffPerSecond, 2)


        # relatório final
        print("\nRELATÓRIO DE USO 😎 (PID {})".format(process.pid))
        print(f"Motivo da finalização: {reason}")
        print(f"Tempo total de CPU (usuário): {last_user_cpu:.2f}s")
        print(f"Tempo total de CPU (sistema): {last_system_cpu:.2f}s")
        print(f"Tempo total de CPU (total): {cpu_total:.2f}s")
        print(f"Pico de uso de memória: {max_memory / (1024 * 1024):.2f} MB")
        print(f"Custo da execução: R${executionCost:.2f}")


        #atualiza os saldos
        if prePago:
            with saldo_lock:
                saldo[0] = round(saldo[0] - executionCost, 2)
                if saldo[0] <= 0:
                    print("[ERRO] Saldo insuficiente. Encerrando todos os processos...")
                    os._exit(0)

        quota_excedida = (reason == "quota_excedida")
        return cpu_total, quota_excedida

    except Exception as e:
        print(f"[ERRO] Erro inesperado: {e}")
        return 0, False


def main():
    print("Bem vindo ao FMS! 😎")
    mode = input("Como gostaria de pagar? [1] Pré-Pago [2] Pós-Pago: ").strip() #pergunta modo de cobrança

    prePago = mode == '1'
    saldo = [0.0]
    saldo_lock = threading.Lock()

    #pede o valor do pré pago
    if prePago:
        try:
            saldo[0] = float(input("Qual o valor do saldo? ").replace(",", "."))
            saldo[0] = round(saldo[0], 2)
        except ValueError:
            print("Valor inválido.")
            return

    #pede a quota de CPU
    try:
        quotaCpu = float(input("Defina a quota total de CPU (em segundos): "))
    except ValueError:
        print("Valor inválido para quota de CPU.")
        return

    #define valor da tarifa
    tariffPerSecond = 0.01

    quota_restante = quotaCpu
    while True:
        print(f"\nSaldo atual: R${saldo[0]:.2f}" if prePago else "\n[MODO PÓS-PAGO]")

        #coleta de dados do usuário
        data = askUserData(quota_restante)

        if data is None:
            print("[INFO] Encerrando o programa manualmente...")
            break

        #inicializa o monitoramento
        cpu_used, quota_excedida = MonitorProcess(
            data, quota_restante, prePago, saldo, tariffPerSecond, saldo_lock
        )

        quota_restante = round(quota_restante - cpu_used, 2)

        if quota_excedida:
            print("[ALERTA] Quota de CPU TOTAL excedida. Encerrando o programa.")
            break

        if quota_restante <= 0:
            print("[INFO] Quota de CPU esgotada. Encerrando o programa.")
            break

    print("\nops cade o processo?")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBati a cabeça no teclado.")
        programa_encerrado = True
        sys.exit(0)