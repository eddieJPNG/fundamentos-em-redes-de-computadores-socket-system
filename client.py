"""
Cliente TCP — Chat Cliente-Servidor com Protocolo Próprio
=========================================================

Conecta a um servidor TCP e troca mensagens usando o protocolo de
aplicação definido em `protocol.py`:

    <TIPO>:<DADOS>\\n

Comandos digitados pelo usuário:
    (texto livre) : envia HELLO:<texto> como mensagem de chat
    /eco <texto>  : envia ECHO:<texto> e imprime o eco do servidor
    /ping         : envia PING e imprime a resposta PONG
    /sair         : envia EXIT e encerra a conexão limpa
"""

import socket
import sys

from protocol import (
    TIPO_ACK,
    TIPO_ECHO,
    TIPO_ERROR,
    TIPO_EXIT,
    TIPO_HELLO,
    TIPO_PING,
    TIPO_PONG,
    criar_mensagem,
    receber_mensagem,
)

# IP e porta do servidor (ex.: python3 client.py 192.168.1.15 5000)
HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
try:
    PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
except ValueError:
    print(f"[Erro] Porta inválida: {sys.argv[2]!r}. Use um número (ex.: 5000).")
    sys.exit(1)

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.settimeout(10)  # evita travar indefinidamente na conexão/leitura

try:
    print(f"[*] Conectando ao servidor em {HOST}:{PORT}...")
    client.connect((HOST, PORT))
    client.settimeout(None)  # após conectar, leitura volta a ser bloqueante
    print("[+] Conectado ao servidor!")
    print("Comandos: '/eco <texto>', '/ping', '/sair' (ou digite uma mensagem).")

    buffer = bytearray()  # acumulador de bytes para o framing (recv parcial)

    while True:
        try:
            texto = input("Você: ")
        except EOFError:
            # Entrada padrão fechada (ex.: Ctrl+D)
            break

        texto = texto.strip()
        if not texto:
            continue

        # Interpreta comandos locais e converte para mensagens do protocolo
        if texto.lower() == "/sair":
            print("[*] Encerrando a conexão...")
            client.sendall(criar_mensagem(TIPO_EXIT, "bye"))
            break
        elif texto.lower() == "/ping":
            client.sendall(criar_mensagem(TIPO_PING))
            continue
        elif texto.lower().startswith("/eco "):
            client.sendall(criar_mensagem(TIPO_ECHO, texto[5:]))
            continue
        else:
            client.sendall(criar_mensagem(TIPO_HELLO, texto))

        # Aguarda a resposta do servidor
        try:
            resultado = receber_mensagem(client, buffer)
        except ValueError as erro:
            print(f"[!] Mensagem inválida do servidor: {erro}")
            continue
        except UnicodeDecodeError:
            print("[!] Recebido dado com encoding inválido do servidor.")
            continue

        if resultado is None:
            print("\n[-] O servidor encerrou a conexão.")
            break

        tipo, dados = resultado
        if tipo == TIPO_ERROR:
            print(f"[!] Servidor respondeu erro de protocolo: {dados}")
        elif tipo == TIPO_PONG:
            print("[Servidor] PONG (conexao ativa)")
        elif tipo == TIPO_ACK:
            print(f"Servidor: {dados}")
        elif tipo == TIPO_ECHO:
            print(f"Servidor (eco): {dados}")
        else:
            print(f"Servidor [{tipo}]: {dados}")

except ConnectionRefusedError:
    print(f"\n[Erro] Conexão recusada por {HOST}:{PORT}.")
    print("Verifique se o servidor está em execução e se a porta está correta.")
except socket.gaierror:
    print(f"\n[Erro] Endereço do servidor inválido: {HOST!r}.")
    print("Use um IP válido (ex.: 192.168.1.15) ou '127.0.0.1' para testes locais.")
except TimeoutError:
    print(f"\n[Erro] Tempo esgotado ao conectar a {HOST}:{PORT}.")
    print("Verifique se o servidor está acessível pela rede.")
except ConnectionResetError:
    print("\n[Erro] Conexão resetada pelo servidor (RST).")
except (BrokenPipeError, ConnectionError) as erro:
    print(f"\n[Erro] Conexão perdida com o servidor: {erro}")
except KeyboardInterrupt:
    print("\n\n[!] Desconectado pelo usuário.")
finally:
    client.close()
    print("[*] Conexão do cliente encerrada.")
