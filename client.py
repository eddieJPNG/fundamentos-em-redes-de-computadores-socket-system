"""
Cliente TCP — Chat Cliente-Servidor com Protocolo Próprio
========================================================

Conecta a um servidor TCP e troca mensagens usando o protocolo de
aplicação definido em `protocol.py`:

    <TIPO>:<DADOS>\\n

Comandos digitados pelo usuário:
    (texto livre) : envia HELLO:<texto> como mensagem de chat
    /eco <texto>  : envia ECHO:<texto> e imprime o eco do servidor
    /ping         : envia PING e imprime a resposta PONG
    /sair         : envia EXIT, lê o BYE do servidor e encerra (FIN limpo)
    /ajuda        : mostra esta ajuda (não envia nada)

IMPORTANTE — sincronismo request/response:
    O protocolo é "lockstep": cada envio deve ser seguido de exatamente
    UMA leitura da resposta correspondente. Enviar sem ler (ou ler sem
    enviar) desloca a conversa em uma mensagem e nunca mais se recupera.
"""

import socket
import sys

from protocol import (
    TIPO_BYE,
    TIPO_ECHO,
    TIPO_ERROR,
    TIPO_EXIT,
    TIPO_HELLO,
    TIPO_MSG,
    TIPO_PING,
    TIPO_PONG,
    TIPOS_SERVIDOR_CLIENTE,
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
client.settimeout(10)  # evita travar indefinidamente na conexão


def imprimir_ajuda() -> None:
    print("Comandos: '/eco <texto>', '/ping', '/sair', '/ajuda' (ou digite uma mensagem).")


try:
    print(f"[*] Conectando ao servidor em {HOST}:{PORT}...")
    client.connect((HOST, PORT))
    client.settimeout(None)  # após conectar, leitura volta a ser bloqueante
    print("[+] Conectado ao servidor!")
    imprimir_ajuda()

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

        baixado = texto.lower()
        sair = False  # marca se, após ler a resposta, devemos encerrar

        # Interpreta comandos locais e converte para mensagens do protocolo.
        # Cada caminho abaixo define `msg`; nenhum envia sem depois ler.
        if baixado == "/sair":
            print("[*] Encerrando a conexão...")
            msg = criar_mensagem(TIPO_EXIT, "bye")
            sair = True
        elif baixado == "/ping":
            msg = criar_mensagem(TIPO_PING)
        elif baixado.startswith("/eco "):
            eco = texto[5:].strip()
            if not eco:
                print("[!] Uso: /eco <texto>")
                continue
            msg = criar_mensagem(TIPO_ECHO, eco)
        elif baixado == "/eco":
            print("[!] Uso: /eco <texto> (faltou o texto a ecoar).")
            continue
        elif baixado == "/ajuda":
            imprimir_ajuda()
            continue
        elif texto.startswith("/"):
            # Comando desconhecido: NÃO vira chat, avisa o usuário
            print(f"[!] Comando desconhecido: {texto.split()[0]}. Use '/ajuda'.")
            continue
        else:
            msg = criar_mensagem(TIPO_HELLO, texto)

        # Envia a mensagem (protegido contra dados acima do MAX_DADOS)
        try:
            client.sendall(msg)
        except ValueError as erro:
            print(f"[!] Mensagem não enviada (tamanho): {erro}")
            continue

        # Aguarda exatamente UMA resposta do servidor (1 envio -> 1 leitura)
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

        # Valida a direção: o cliente só aceita tipos S -> C
        tipo, dados = resultado
        if tipo not in TIPOS_SERVIDOR_CLIENTE:
            print(f"[!] Tipo inesperado do servidor (direção errada): {tipo}")
            if sair:
                break
            continue

        if tipo == TIPO_ERROR:
            print(f"[!] Servidor respondeu erro de protocolo: {dados}")
        elif tipo == TIPO_PONG:
            print("[Servidor] PONG (conexao ativa)")
        elif tipo == TIPO_MSG:
            print(f"Servidor: {dados}")
        elif tipo == TIPO_BYE:
            print(f"Servidor encerrou: {dados}")
        elif tipo == TIPO_ECHO:
            print(f"Servidor (eco): {dados}")
        else:
            print(f"Servidor [{tipo}]: {dados}")

        # Só encerra DEPOIS de ler a resposta (evita RST por dado não lido)
        if sair:
            break

except ConnectionRefusedError:
    print(f"\n[Erro] Conexão recusada por {HOST}:{PORT}.")
    print("Verifique se o servidor está em execução e se a porta está correta.")
except socket.gaierror:
    print(f"\n[Erro] Endereço do servidor inválido: {HOST!r}.")
    print("Use um IP válido (ex.: 192.168.1.15) ou '127.0.0.1' para testes locais.")
except (socket.timeout, TimeoutError):
    # socket.timeout é alias de TimeoutError só a partir do Python 3.10;
    # capturar os dois garante compatibilidade com Python 3.8/3.9.
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
