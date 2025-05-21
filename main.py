# código principal 

import subprocess
import threading
import time
import psutil
import os
import sys

def askUserData(): # coletar informações do usuário
    binaryName = input("digitar o caminho do programa a ser executado (ex: C:\\\\Windows\\\\System32\\\\notepad.exe): ") 
    try:
        quotaCpu = float(input("informar a quota de tempo de CPU (em segundos): "))
        timeout = float(input("informar o tempo limite total de execução (em segundos): ")) 
        memoryLimit = float(input("informar o limite máximo de memória (em mb): "))

    except ValueError:
        print("entrada inválida")
        return None

    return {
        "binary": binaryName,
        "quotaCpu": quotaCpu,
        "timeout": timeout,
        "limiteMemoria": memoryLimit * 1024 * 1024  # mb para bytes verificarisso
    }


def runBinary(data):
    try:
        process = subprocess.Popen(data['binary'],shell=True) #abre
        pid = process.pid
        print(f'pid do processo: {pid}')

        startTime = time.time() #guarda tempo de inicio

        #thread para monitorar o processo
        monitorThread = threading.Thread(target=monitorProcess, args=(data, process))
        monitorThread.start() #inicia a thread
        cpu_thread = threading.Thread(target=monitorCPU, args=(data, process))
        mem_thread = threading.Thread(target=monitorMemory, args=(data, process))
        
        cpu_thread.start()
        mem_thread.start()

        while True: #espera i timeout
            tempoPassado = time.time() - startTime #atualizar esse nome aqui pelo amro de daeus

            if process.poll() is not None: #ele verifica se terminou o processo
                print(f'processo finalizado {tempoPassado:.2f}')

            if tempoPassado >= data['timeout']: #verificação do timeout
                process.kill() #fecha
                print(f'processo encerrado {tempoPassado:.2f}')
                break

            time.sleep(0.5)

    except FileNotFoundError:
        print("arquivo não encontrado")
    except Exception as e:
        print(f"erro inesperado: {e}")
        
        
def monitorCPU(data, process):
    try:
        psProcess = psutil.Process(process.pid)
        while process.poll() is None:
            cpu_times = psProcess.cpu_times()
            cpu_total = cpu_times.user + cpu_times.system
            percent_used = (cpu_total / data['quotaCpu']) * 100

            status = f"[CPU] Uso: {cpu_total:.2f}s / {data['quotaCpu']}s ({percent_used:.1f}%)"
            if percent_used >= 90:
                status += "[CPU] alerta!"
            print(status)

            if cpu_total >= data['quotaCpu']:
                print("[CPU] quota esgotada.")
                process.kill()
                break

            time.sleep(1)  # atualiza a cada 1 segundo

    except psutil.NoSuchProcess:
        print("[CPU] processo terminou")
    
        
def get_total_memory_usage(ps_proc):
    try:
        total = ps_proc.memory_info().rss
        for child in ps_proc.children(recursive=True):
            total += child.memory_info().rss
        return total
    except psutil.NoSuchProcess:
        return 0


def monitorMemory(data, process):
    try:
        psProcess = psutil.Process(process.pid)
        while process.poll() is None:
            memory_usage = get_total_memory_usage(psProcess)
            memory_mb = memory_usage / (1024 * 1024)
            limit_mb = data['limiteMemoria'] / (1024 * 1024)
            percent_used = (memory_usage / data['limiteMemoria']) * 100

            status = f"[MEM] Uso: {memory_mb:.2f}MB / {limit_mb:.2f}MB ({percent_used:.1f}%)"
            if percent_used >= 90:
                status += " [MEM] alerta!"
            print(status)

            if memory_usage >= data['limiteMemoria']:
                print("[MEM] memória insuficiente.")
                process.kill()
                break

            time.sleep(1)
    except psutil.NoSuchProcess:
        print("[MEM] processo terminou")



def monitorProcess(data, process):
    try:
        psProcess = psutil.Process(process.pid)

        while process.poll() is None:
            #uso da cpu
            cpu_times = psProcess.cpu_times()
            cpuUser = cpu_times.user
            cpuSystem = cpu_times.system
            cpuTotal = cpu_times.user + cpu_times.system

            #uso da memoria
            memory_info = psProcess.memory_info()
            memory_usage = psProcess.memory_info().rss

            # essa linha ta bem podi so que quis preservar a ordem dela dps arrumo
            print(f'uso da CPU User: {cpuUser:.2f} s, uso da CPU Total: {cpuTotal:.2f} s, uso da CPU System: {cpuSystem:.2f}, uso da memória: {memory_info.vms / (1024 * 1024):.2f} mb')

            #cheacagem de tempo
            if cpuTotal >= data['quotaCpu']:
                print("[CPU] quota esgotada")
                sys.exit("encerrando!!!!!!")

            if memory_usage >= data['limiteMemoria']:
                print("limite de memória excedido")
                process.kill()
                break
            
            time.sleep(1)

    except psutil.NoSuchProcess:
        print("processo não encontrado")


if __name__ == "__main__":
    while True:
        data = askUserData()
        if not data:
            continue
        runBinary(data)