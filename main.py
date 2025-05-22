import subprocess
import threading
import time
import psutil
import os

#coleta dados do usuario
def askUserData():
    binaryPath = input("Caminho do programa (ex: C:\\Windows\\System32\\notepad.exe): ").strip()

    if binaryPath.lower() == "sair": #permite usuario sair
        return None

    try:
        quotaCpu = float(input("Quota de CPU (em segundos): "))
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

#monitoramento em tempo real
def monitorProcess(data, initial_pid):
    try:
        process = psutil.Process(initial_pid)

    except psutil.NoSuchProcess: #ja foi encerrado
        return None 

    startTime = time.time()
    max_memory = 0
    last_user_cpu = 0
    last_system_cpu = 0
    reason = "finalizado normalmente"

    while True:
        elapsedTime = time.time() - startTime

        if process is None or not process.is_running():
            process = selectActiveProcess(data['binaryName']) #tenta encontrar outro com o mesmo nome
            if process is None:
                print("[INFO] Nenhum processo ativo encontrado. Encerrando monitoramento.")
                break
            else:
                print(f"[INFO] Mudando para o novo processo PID={process.pid}")

        try:
            cpu_times = process.cpu_times()
            cpu_user = cpu_times.user
            cpu_system = cpu_times.system
            cpu_total = cpu_user + cpu_system

            memory_usage = process.memory_info().rss #uso em bytes
            if memory_usage > max_memory:
                max_memory = memory_usage #atualiza o pico de uso de memoria

            print(f'[MONITOR] CPU: {cpu_total:.2f} s (Usuário: {cpu_user:.2f}s | Sistema: {cpu_system:.2f}s), ' f'MEM: {memory_usage / (1024 * 1024):.2f} MB | Tempo: {elapsedTime:.2f}s')

            # verifica se o limite foi ultrapassado
            if cpu_total >= data['quotaCpu']:
                print("[ALERTA] Quota de CPU excedida. encerrando processo.")
                process.kill()
                reason = "quota_excedida"
                break

            if memory_usage >= data['limiteMemoria']:
                print("[ALERTA] Limite de memória excedido. encerrando processo.")
                process.kill()
                reason = "memoria_excedida"
                break

            if elapsedTime >= data['timeout']:
                print("[ALERTA] Tempo limite excedido. encerrando processo.")
                process.kill()
                reason = "tempo_excedido"
                break

            # salva para relatorio
            last_user_cpu = cpu_user
            last_system_cpu = cpu_system

            time.sleep(1)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print("[INFO] Processo inacessível ou encerrado.")
            process = None #tenta encontrar outro com o mesmo nome

    #retorna as estatísticas finais
    return {
        "cpu_user": last_user_cpu,
        "cpu_system": last_system_cpu,
        "memory_peak": max_memory,
        "motivo_finalizacao": reason
    }


#executa o binario e inicia o monitoramento
def run_binary(data):
    try:
        cmd = f'cmd /c start "" "{data["binaryPath"]}"' #comando para abrir o binário
        print(f"[INFO] Executando: {cmd}")
        subprocess.Popen(cmd, shell=True) #inicia o binário

        time.sleep(3) #ele garante que o processo seja iniciado
        process = selectActiveProcess(data['binaryName'])

        if not process:
            print("[ERRO] Processo não encontrado apos iniciar.")
            return None

        print(f"[INFO] Processo inicial detectado: PID={process.pid} ({process.name()})")

        #cria uma thread para monitorar o processo
        monitorThread = threading.Thread(
            target=monitorProcess, args=(data, process.pid)
        )
        monitorThread.start()
        monitorThread.join() # espera o monitoramento terminar

        return monitorProcess(data, process.pid)

    except Exception as e:
        print(f"[ERRO] Erro inesperado: {e}")
        return None



def main():
    quota_excedida = False

    while not quota_excedida:
        data = askUserData()
        if data is None:
            print("saindo...")
            break

        result = run_binary(data)

        print("Execução concluída.")
        print("===============================================")

        if result:
            print("RELATÓRIO DE USO 😎 ")
            print(f"Tempo total de CPU (usuário): {result['cpu_user']:.2f}s")
            print(f"Tempo total de CPU (sistema): {result['cpu_system']:.2f}s")
            print(f"Tempo total de CPU (total): {result['cpu_user'] + result['cpu_system']:.2f}s")
            print(f"Pico de uso de memória: {result['memory_peak'] / (1024 * 1024):.2f} MB")
            print("===============================================")

            if result.get("motivo_finalizacao") == "quota_excedida":
                print("[INFO] Quota de CPU foi excedida. Encerrando o programa completamente.")
                quota_excedida = True
        else:
            print("ops cade o processo?")

        if not quota_excedida:
            print("Digite 'sair' para encerrar.\n")


if __name__ == "__main__":
    main()