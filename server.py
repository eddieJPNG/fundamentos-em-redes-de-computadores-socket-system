"""
Servidor TCP — Chat Cliente-Servidor com Protocolo Próprio
==========================================================

Escuta conexões de clientes na porta definida (padrão 5000) e troca
mensagens usando o protocolo de aplicação definido em `protocol.py`:

    <TIPO>:<DADOS>\\n

Tipos aceitos do cliente:
    HELLO : mensagem de chat (impressa e confirmada com ACK)
    ECHO  : o servidor devolve os mesmos dados (ECHO:<dados>)
    PING  : responde PONG
    EXIT  : encerra a sessão

Erros de protocolo são respondidos com ERROR:<motivo> sem derrubar o servidor.
"""

import socket
import sys

from protocol import (
    DELIMITADOR,
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

HOST = "0.0.0.0"  # escuta em todas as interfaces de rede
try:
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
except ValueError:
    print(f"[Erro] Porta inválida: {sys.argv[1]!r}. Use um número (ex.: 5000).")
    sys.exit(1)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Reutiliza a porta imediatamente após reinício (evita "Address already in use")
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    try:
        server.bind((HOST, PORT))
    except OSError as erro:
        print(f"[Erro] Não foi possível abrir a porta {PORT}: {erro}")
        print("Verifique se ela já está em uso ou se há permissão (portas < 1024).")
        sys.exit(1)

    server.listen(1)

    print("=" * 48)
    print("        SERVIDOR TCP INICIADO (protocolo próprio)")
    print(f"  Endereço de escuta : {HOST}:{PORT}")
    print("  Aguardando conexão de um cliente...")
    print("  (Pressione Ctrl+C para encerrar o servidor)")
    print("=" * 48)

    conn, address = server.accept()
    print(f"\n[+] Cliente conectado: {address[0]}:{address[1]}")
    print(f"[i] Protocolo: <TIPO>:<DADOS>{DELIMITADOR!r}\n")

    buffer = bytearray()  # acumulador de bytes para o framing (recv parcial)

    try:
        while True:
            try:
                resultado = receber_mensagem(conn, buffer)
            except ValueError as erro:
                # Mensagem malformada: avisa o cliente e continua no loop
                print(f"[!] Mensagem inválida recebida: {erro}")
                conn.sendall(criar_mensagem(TIPO_ERROR, f"formato_invalido: {erro}"))
                continue
            except UnicodeDecodeError:
                print("[!] Recebido dado com encoding inválido.")
                conn.sendall(criar_mensagem(TIPO_ERROR, "encoding_invalido"))
                continue

            if resultado is None:
                # recv devolveu b'' => cliente enviou FIN (desconectou)
                print("\n[-] O cliente encerrou a conexão.")
                break

            tipo, dados = resultado
            print(f" Cliente [{tipo}]: {dados}")

            if tipo == TIPO_HELLO:
                try:
                    resposta = input(" Servidor: ")
                except EOFError:
                    # Entrada padrão fechada (ex.: pipe encerrado)
                    conn.sendall(criar_mensagem(TIPO_ACK, "servidor_encerrando"))
                    break
                conn.sendall(criar_mensagem(TIPO_ACK, resposta))

            elif tipo == TIPO_ECHO:
                conn.sendall(criar_mensagem(TIPO_ECHO, dados))

            elif tipo == TIPO_PING:
                conn.sendall(criar_mensagem(TIPO_PONG, ""))

            elif tipo == TIPO_EXIT:
                conn.sendall(criar_mensagem(TIPO_ACK, "sessao_encerrada"))
                print("[*] Cliente solicitou o encerramento da sessão.")
                break

    except ConnectionResetError:
        print("\n[-] Conexão resetada pelo cliente (RST).")
    except (BrokenPipeError, ConnectionError) as erro:
        print(f"\n[-] Conexão perdida com o cliente: {erro}")
    finally:
        conn.close()
        print("[*] Conexão com o cliente fechada.")

except KeyboardInterrupt:
    print("\n\n[!] Servidor finalizado pelo usuário.")
finally:
    server.close()
    print("[*] Socket do servidor finalizado com sucesso.")
