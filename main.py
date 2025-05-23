import subprocess
import threading
import time
import psutil
import os
import sys


def askUserData(quota_restante):
    print(f"\nQuota de CPU restante: {quota_restante:.2f} segundos")
    binaryPath = input("Caminho do programa (ex: C:\\Windows\\System32\\notepad.exe): ").strip()

    if binaryPath.lower() == "sair":
        return None

    try:
        timeout = float(input("Tempo limite de execução (em segundos): "))
        memoryLimit = float(input("Limite máximo de memória (em MB): ")) * 1024 * 1024
    except ValueError:
        print("Entrada inválida")
        return None

    return {
        "binaryPath": binaryPath,
        "binaryName": os.path.basename(binaryPath),
        "timeout": timeout,
        "limiteMemoria": memoryLimit
    }


def findProcessByName(name):
    matching = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == name.lower():
                matching.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return matching


def selectActiveProcess(binaryName):
    processes = findProcessByName(binaryName)
    if not processes:
        return None
    process = sorted(processes, key=lambda p: p.create_time())[-1]
    return process


def all_killed(proc):
    try:
        children = proc.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        proc.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


def MonitorProcess(data, quota_restante, prePago, saldo, tariffPerSecond, saldo_lock):
    try:
        cmd = f'cmd /c start "" "{data["binaryPath"]}"'
        print("[INFO] Executando:")
        subprocess.Popen(cmd, shell=True)

        time.sleep(3)
        process = selectActiveProcess(data['binaryName'])

        if not process:
            print("[ERRO] Processo não encontrado após iniciar.")
            return 0, False

        print(f"[INFO] Processo detectado: PID={process.pid} ({process.name()})")

        startTime = time.time()
        max_memory = 0
        last_user_cpu = 0
        last_system_cpu = 0
        reason = "finalizado_normalmente"

        while True:
            elapsedTime = time.time() - startTime

            if not process.is_running():
                break

            try:
                cpu_times = process.cpu_times()
                cpu_user = cpu_times.user
                cpu_system = cpu_times.system
                cpu_total = cpu_user + cpu_system

                memory_usage = process.memory_info().rss
                if memory_usage > max_memory:
                    max_memory = memory_usage

                print(f'[MONITOR | PID={process.pid}] CPU: {cpu_total:.2f}s | MEM: {memory_usage / (1024 * 1024):.2f}MB | Tempo: {elapsedTime:.2f}s')

                if cpu_total >= quota_restante:
                    print(f"[ALERTA | PID={process.pid}] Quota de CPU excedida. Encerrando processo.")
                    all_killed(process)
                    reason = "quota_excedida"
                    break

                if memory_usage >= data['limiteMemoria']:
                    print(f"[ALERTA | PID={process.pid}] Limite de memória excedido.")

                if elapsedTime >= data['timeout']:
                    print(f"[INFO | PID={process.pid}] Tempo limite atingido.")
                    reason = "tempo_excedido"
                    all_killed(process)
                    break

                last_user_cpu = cpu_user
                last_system_cpu = cpu_system

                time.sleep(1)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"[INFO | PID={process.pid}] Processo inacessível ou encerrado.")
                break

        cpu_total = last_user_cpu + last_system_cpu
        executionCost = round(cpu_total * tariffPerSecond, 2)

        print("\nRELATÓRIO DE USO 😎 (PID {})".format(process.pid))
        print(f"Motivo da finalização: {reason}")
        print(f"Tempo total de CPU (usuário): {last_user_cpu:.2f}s")
        print(f"Tempo total de CPU (sistema): {last_system_cpu:.2f}s")
        print(f"Tempo total de CPU (total): {cpu_total:.2f}s")
        print(f"Pico de uso de memória: {max_memory / (1024 * 1024):.2f} MB")
        print(f"Custo da execução: R${executionCost:.2f}")

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
    mode = input("Como gostaria de pagar? [1] Pré-Pago [2] Pós-Pago: ").strip()

    prePago = mode == '1'
    saldo = [0.0]
    saldo_lock = threading.Lock()

    if prePago:
        try:
            saldo[0] = float(input("Qual o valor do saldo? ").replace(",", "."))
            saldo[0] = round(saldo[0], 2)
        except ValueError:
            print("Valor inválido.")
            return

    try:
        quotaCpu = float(input("Defina a quota total de CPU (em segundos): "))
    except ValueError:
        print("Valor inválido para quota de CPU.")
        return

    tariffPerSecond = 0.01

    quota_restante = quotaCpu
    while True:
        print(f"\nSaldo atual: R${saldo[0]:.2f}" if prePago else "\n[MODO PÓS-PAGO]")

        data = askUserData(quota_restante)

        if data is None:
            print("[INFO] Encerrando o programa manualmente...")
            break

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