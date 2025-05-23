import subprocess
import threading
import time
import psutil
import os

quota_excedida = False

#coleta dados do usuario
def askUserData():
    binaryPath = input("Caminho do programa (ex: C:\\Windows\\System32\\notepad.exe): ").strip()

    if binaryPath.lower() == "sair": #permite usuario sair
        return None
    
    quotaCpu = float(input("Quota de CPU (em segundos): "))

    if quota_excedida == False:
        try:
            timeout = float(input("Tempo limite total de execução (em segundos): "))
            memoryLimit = float(input("Limite máximo de memória (em MB): ")) * 1024 * 1024 #mb para bytes
        except ValueError:
            print("Entrada inválida")
            return None

    return {
        "binaryPath": binaryPath,
        "binaryName": os.path.basename(binaryPath),
        "quotaCpu": quotaCpu,
        "timeout": timeout,
        "limiteMemoria": memoryLimit
    }


# encontra todos os processos ativos pelo nome do executavel
def findProcessByName(name):
    matching = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == name.lower():
                matching.append(proc)

        except (psutil.NoSuchProcess, psutil.AccessDenied): # ignora processos q não podem ser acessados
            continue

    return matching


# seleciona o processo mais recente com o nome informado
def selectActiveProcess(binaryName):
    processes = findProcessByName(binaryName)
    if not processes:
        return None

    # ordena por tempo de criação e pega o processo mais recente
    process = sorted(processes, key=lambda p: p.create_time())[-1]
    return process

def kill_process_and_children(proc):
    try:
        children = proc.children(recursive=True)
        for child in children:
            try:
                print(f"Encerrando filho PID={child.pid}")
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        print(f"Encerrando pai PID={proc.pid}")
        proc.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


#monitoramento em tempo real

def monitorProcess(data, initial_pid):
    try:
        process = psutil.Process(initial_pid)
    except psutil.NoSuchProcess:
        return None

    startTime = time.time()
    max_memory = 0
    last_user_cpu = 0
    last_system_cpu = 0
    reason = "finalizado normalmente"

    aviso_75 = aviso_90 = False

    while True:
        elapsedTime = time.time() - startTime

        if not process.is_running() or process.status() in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
            print("[ALERTA] Processo encerrado manualmente pelo usuário.")
            reason = "usuario_encerrado"
            break

        try:
            cpu_times = process.cpu_times()
            cpu_user = cpu_times.user
            cpu_system = cpu_times.system
            cpu_total = cpu_user + cpu_system

            memory_usage = process.memory_info().rss
            if memory_usage > max_memory:
                max_memory = memory_usage

            print(f'[MONITOR] CPU: {cpu_total:.2f}s (Usuário: {cpu_user:.2f}s | Sistema: {cpu_system:.2f}s), '
                  f'MEM: {memory_usage / (1024 * 1024):.2f} MB | Tempo: {elapsedTime:.2f}s')

            # ALERTAS DE CPU
            quota = data['quotaCpu']
            if not aviso_75 and cpu_total >= 0.75 * quota:
                print(f"[AVISO] 75% da quota de CPU ({quota:.2f}s) já foi utilizada.")
                aviso_75 = True
            if not aviso_90 and cpu_total >= 0.90 * quota:
                print(f"[AVISO] 90% da quota de CPU atingida! Restam poucos segundos.")
                aviso_90 = True

            # VERIFICAÇÕES
            
            if cpu_total >= quota:
                print("[ALERTA] Quota de CPU excedida. Encerrando processo e filhos...")
                kill_process_and_children(process)
                reason = "quota_excedida"
                break

            if memory_usage >= data['limiteMemoria']:
                print("[AVISO] Limite de memória excedido.")
                # Apenas alerta, sem finalizar

            if elapsedTime >= data['timeout']:
                print("[ALERTA] Tempo limite excedido. Encerrando processo.")
                kill_process_and_children(process)
                reason = "tempo_excedido"
                break

            last_user_cpu = cpu_user
            last_system_cpu = cpu_system
            time.sleep(1)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print("[ALERTA] Processo inacessível ou encerrado manualmente.")
            reason = "usuario_encerrado"
            break

    print(f"[INFO] Monitoramento encerrado. Motivo: {reason}")
    return {
        "cpu_user": last_user_cpu,
        "cpu_system": last_system_cpu,
        "memory_peak": max_memory,
        "motivo_finalizacao": reason
    }



#executa o binario e inicia o monitoramento
def run_binary(data):
    try:
        cmd = f'cmd /c start "" "{data["binaryPath"]}"'
        print(f"Executando: {cmd}")
        subprocess.Popen(cmd, shell=True)

        time.sleep(3)
        process = selectActiveProcess(data['binaryName'])

        if not process:
            print("[ERRO] Processo não encontrado após iniciar.")
            return None

        print(f"[INFO] Processo inicial detectado: PID={process.pid} ({process.name()})")

        # Monitoramento direto (sem usar thread extra)
        result = monitorProcess(data, process.pid)

        # Se processo foi encerrado manualmente, tente finalizar filhos e pai
        if result and result.get("motivo_finalizacao") == "usuario_encerrado":
            print("[INFO] Tentando encerrar processo e filhos (usuário fechou a janela)...")
            try:
                proc = psutil.Process(process.pid)
                if proc.is_running():
                    kill_process_and_children(proc)
            except psutil.NoSuchProcess:
                pass

        return result

    except Exception as e:
        print(f"[ERRO] Erro inesperado: {e}")
        return None

def main():
    print("Bem vindo ao FMS! 😎")
    mode = input("Como gostaria de pagar? [1] Pré-Pago [2] Pós-Pago: ").strip()

    prePago = mode == '1'
    saldo = 0.0

    if prePago:
        try:
            saldo = float(input("Qual o valor do saldo? ").replace(",", "."))
            saldo = round(saldo, 2)
        except ValueError:
            print("Valor inválido.")
            return

    tariffPerSecond = 0.01  # R$0,01 por segundo de CPU

    quota_excedida = usuario_encerrado = False

    while quota_excedida != True:
        print(f"\nSeu saldo atual: R${saldo:.2f}" if prePago else "\n[MODO PÓS-PAGO]")
        data = askUserData()
        if data is None:
            print("saindo...")
            break

        if prePago:
            maxCost = round(data['quotaCpu'] * tariffPerSecond, 2)
            if saldo < maxCost:
                print(f"[ERRO] Saldo insuficiente. Custo estimado: R${maxCost:.2f}")
                print(f"Saldo atual: R${saldo:.2f}")
                break

        result = run_binary(data)

        print("Execução concluída.")
        print("===============================================")

        if result:
            CPUTotaltime = result['cpu_user'] + result['cpu_system']
            executionCost = round(CPUTotaltime * tariffPerSecond, 2)

            print("RELATÓRIO DE USO 😎")
            print(f"Tempo total de CPU (usuário): {result['cpu_user']:.2f}s")
            print(f"Tempo total de CPU (sistema): {result['cpu_system']:.2f}s")
            print(f"Tempo total de CPU (total): {CPUTotaltime:.2f}s")
            print(f"Pico de uso de memória: {result['memory_peak'] / (1024 * 1024):.2f} MB")

            if prePago:
                print(f"Valor total: R${executionCost:.2f}")
                saldo = round(saldo - executionCost, 2)
                print(f"Saldo restante: R${saldo:.2f}")
                if saldo <= 0:
                    print("Saldo insuficiente. Encerrando o programa...")
                    break
            else:
                print(f"\nCusto calculado (pós-pago): R${executionCost:.2f}")

            print("===============================================")

            motivo = result.get("motivo_finalizacao")
            if motivo == "quota_excedida":
                print("Quota de CPU foi excedida :(")
                quota_excedida = True
            elif motivo == "usuario_encerrado":
                print("Programa encerrado manualmente.")
                usuario_encerrado = True
        else:
            print("ops, cadê o processo?")

    print("Programa finalizado.")



if __name__ == "__main__":
    main()