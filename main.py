# código principal 
import subprocess
import threading
import time
# import psutil
import os

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
        process = subprocess.Popen(data['binary'],shell=False) #abre
        pid = process.pid
        print(f'pid do processo: {pid}')

        startTime = time.time() #guarda tempo de inicio

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




if __name__ == "__main__": #teste teste teste teste
    data = askUserData()
    if data:
        print(data)
        runBinary(data)
    else:
        print("erro tenta de novo 😋")