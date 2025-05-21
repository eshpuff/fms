import subprocess
import threading
import time
import psutil
import os

def askUserData():
    binaryPath = input("Caminho do programa (ex: C:\\Windows\\System32\\notepad.exe): ").strip()

    if binaryPath.lower() == "sair":
        return None

    try:
        quotaCpu = float(input("Quota de CPU (em segundos): "))
        timeout = float(input("Tempo limite total de execução (em segundos): "))
        memoryLimit = float(input("Limite máximo de memória (em MB): ")) * 1024 * 1024
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

def find_process_by_name(name):
    # encontra todos os processos ativos pelo nome do binary
    matching = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == name.lower():
                matching.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return matching


def select_active_process(binaryName):
    # seleciona o processo mais recente com o nome informado
    processes = find_process_by_name(binaryName)
    if not processes:
        return None

    # ordena por tempo de criação e pega o processo mais recente
    process = sorted(processes, key=lambda p: p.create_time())[-1]
    return process


def monitor_process(data, initial_pid):
    try:
        process = psutil.Process(initial_pid)
    except psutil.NoSuchProcess:
        return None

    startTime = time.time()
    max_memory = 0
    last_user_cpu = 0
    last_system_cpu = 0
    reason = "finalizado normalmente"

    while True:
        elapsedTime = time.time() - startTime

        if process is None or not process.is_running():
            process = select_active_process(data['binaryName'])
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

            memory_usage = process.memory_info().rss
            if memory_usage > max_memory:
                max_memory = memory_usage

            print(f'[MONITOR] CPU: {cpu_total:.2f} s (Usuário: {cpu_user:.2f}s | Sistema: {cpu_system:.2f}s), '
                  f'MEM: {memory_usage / (1024 * 1024):.2f} MB | Tempo: {elapsedTime:.2f}s')

            if cpu_total >= data['quotaCpu']:
                print("[ALERTA] Quota de CPU excedida. Encerrando processo.")
                process.kill()
                reason = "quota_excedida"
                break

            if memory_usage >= data['limiteMemoria']:
                print("[ALERTA] Limite de memória excedido. Encerrando processo.")
                process.kill()
                reason = "memoria_excedida"
                break

            if elapsedTime >= data['timeout']:
                print("[ALERTA] Tempo limite excedido. Encerrando processo.")
                process.kill()
                reason = "tempo_excedido"
                break

            last_user_cpu = cpu_user
            last_system_cpu = cpu_system

            time.sleep(1)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print("[INFO] Processo inacessível ou encerrado.")
            process = None

    return {
        "cpu_user": last_user_cpu,
        "cpu_system": last_system_cpu,
        "memory_peak": max_memory,
        "motivo_finalizacao": reason
    }



def run_binary(data):
    try:
        cmd = f'cmd /c start "" "{data["binaryPath"]}"'
        print(f"[INFO] Executando: {cmd}")
        subprocess.Popen(cmd, shell=True)

        time.sleep(3)
        process = select_active_process(data['binaryName'])

        if not process:
            print("[ERRO] Processo não encontrado após iniciar.")
            return None

        print(f"[INFO] Processo inicial detectado: PID={process.pid} ({process.name()})")

        monitorThread = threading.Thread(
            target=monitor_process, args=(data, process.pid)
        )
        monitorThread.start()
        monitorThread.join()

        return monitor_process(data, process.pid)

    except Exception as e:
        print(f"[ERRO] Erro inesperado: {e}")
        return None



def main():
    quota_excedida = False

    while not quota_excedida:
        data = askUserData()
        if data is None:
            print("Saindo...")
            break

        result = run_binary(data)

        print("Execução concluída.")
        print("===============================================")

        if result:
            print(" ♥  RELATÓRIO DE USO :DD ")
            print(f"Tempo total de CPU (usuário): {result['cpu_user']:.2f}s")
            print(f"Tempo total de CPU (sistema): {result['cpu_system']:.2f}s")
            print(f"Tempo total de CPU (total): {result['cpu_user'] + result['cpu_system']:.2f}s")
            print(f"Pico de uso de memória: {result['memory_peak'] / (1024 * 1024):.2f} MB")
            print("==============================")

            if result.get("motivo_finalizacao") == "quota_excedida":
                print("[INFO] Quota de CPU foi excedida. Encerrando o programa completamente.")
                quota_excedida = True
        else:
            print("não")

        if not quota_excedida:
            print("Digite 'sair' para encerrar.\n")


if __name__ == "__main__":
    main()