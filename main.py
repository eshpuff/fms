# funciona com notepad e paint, mas nao com a calculadora. tem q ver pq

import subprocess
import threading
import time
import psutil
import os
import shutil

def askUserData():
    binaryName = input("Caminho do programa a ser executado (ex: C:\\\\Windows\\\\System32\\\\notepad.exe ou apenas notepad.exe): ") 
    try:
        quotaCpu = float(input("Quota de tempo de CPU (s): "))
        timeout = float(input("Tempo limite total de execução (s): ")) 
        memoryLimit = float(input("Limite máximo de memória (MB): "))
    except ValueError:
        print("Entrada inválida.")
        return None

    return {
        "binary": binaryName.strip(),
        "quotaCpu": quotaCpu,
        "timeout": timeout,
        "limiteMemoria": memoryLimit * 1024 * 1024  # MB → bytes
    }
    
    
#chat!!!
def diferenca_processos(proc_antigo, proc_novo):
    return [p for p in proc_novo if p.pid not in [x.pid for x in proc_antigo]]

def get_total_memory_usage(ps_proc):
    try:
        total = ps_proc.memory_info().rss
        for child in ps_proc.children(recursive=True):
            total += child.memory_info().rss
        return total
    except psutil.NoSuchProcess:
        return 0

def monitorCPU(data, psProcess):
    while psProcess.is_running():
        try:
            cpu_times = psProcess.cpu_times()
            cpu_total = cpu_times.user + cpu_times.system
            percent_used = (cpu_total / data['quotaCpu']) * 100

            status = f"[CPU] Uso: {cpu_total:.2f}s / {data['quotaCpu']}s ({percent_used:.1f}%)"
            if percent_used >= 90:
                status += " [ALERTA]"
            print(status)

            if cpu_total >= data['quotaCpu']:
                print("[CPU] Quota esgotada. Encerrando processo.")
                psProcess.kill()
                break

            time.sleep(1)
        except psutil.NoSuchProcess:
            break

def monitorMemory(data, psProcess):
    while psProcess.is_running():
        try:
            memory_usage = get_total_memory_usage(psProcess)
            memory_mb = memory_usage / (1024 * 1024)
            limit_mb = data['limiteMemoria'] / (1024 * 1024)
            percent_used = (memory_usage / data['limiteMemoria']) * 100

            status = f"[MEM] Uso: {memory_mb:.2f}MB / {limit_mb:.2f}MB ({percent_used:.1f}%)"
            if percent_used >= 90:
                status += " [ALERTA]"
            print(status)

            if memory_usage >= data['limiteMemoria']:
                print("[MEM] Limite de memória excedido. Encerrando processo.")
                psProcess.kill()
                break

            time.sleep(1)
        except psutil.NoSuchProcess:
            print("[MEM] Processo terminou.")
            break

#chat chat
def runBinary(data):
    try:
        caminho = data['binary']
        nome_base = os.path.basename(caminho).lower()

        # Se for caminho completo, verifica se existe
        if os.path.sep in caminho and not os.path.exists(caminho):
            print("[ERRO] Caminho não encontrado:", caminho)
            return

        # Se não for caminho completo, verifica se está no PATH
        if os.path.sep not in caminho and not shutil.which(caminho):
            print(f"[ERRO] '{caminho}' não encontrado no PATH do sistema.")
            return

        processos_antes = list(psutil.process_iter(['pid', 'name']))
        processo_tmp = subprocess.Popen([caminho])
        print(f'[INFO] Processo inicial (transitório) PID: {processo_tmp.pid}')

        time.sleep(1.5)

        processos_depois = list(psutil.process_iter(['pid', 'name']))
        novos = diferenca_processos(processos_antes, processos_depois)

        # Tenta identificar o processo pelo nome
        processos_finais = [p for p in novos if nome_base in p.info['name'].lower()]

        if not processos_finais:
            print("[AVISO] Nenhum processo identificado diretamente. O programa pode estar rodando como processo UWP (ex: Calculadora).")
            return

        psProcess = processos_finais[0]
        print(f"[INFO] Processo real detectado: PID {psProcess.pid} ({psProcess.name()})")

        startTime = time.time()

        cpu_thread = threading.Thread(target=monitorCPU, args=(data, psProcess))
        mem_thread = threading.Thread(target=monitorMemory, args=(data, psProcess))
        cpu_thread.start()
        mem_thread.start()

        while True:
            tempoPassado = time.time() - startTime

            if not psProcess.is_running():
                print(f"[INFO] Processo finalizado após {tempoPassado:.2f}s")
                break

            if tempoPassado >= data['timeout']:
                print(f"[INFO] Tempo limite atingido ({tempoPassado:.2f}s). Encerrando processo.")
                psProcess.kill()
                break

            time.sleep(0.5)
            
        cpu_thread.join()
        mem_thread.join()

    except FileNotFoundError:
        print("[ERRO] Arquivo não encontrado.")
    except Exception as e:
        print(f"[ERRO] Erro inesperado: {e}")

if __name__ == "__main__":
    while True:
        data = askUserData()
        if not data:
            continue
        runBinary(data)