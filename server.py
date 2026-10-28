"""
Servidor TCP — Chat Cliente-Servidor com Protocolo Próprio
=========================================================

Escuta conexões de clientes na porta definida (padrão 5000) e troca
mensagens usando o protocolo de aplicação definido em `protocol.py`:

    <TIPO>:<DADOS>\\n

Tipos aceitos do cliente (C -> S):
    HELLO : mensagem de chat (impressa e respondida com MSG pelo operador)
    ECHO  : o servidor devolve os mesmos dados (ECHO:<dados>)
    PING  : responde PONG
    EXIT  : encerra a sessão (responde BYE e fecha)

Tipos enviados ao cliente (S -> C):
    MSG   : resposta do operador ao chat
    PONG  : resposta ao PING
    ECHO  : eco dos dados
    BYE   : sessão encerrada / servidor saindo
    ERROR : erro de protocolo (sem derrubar o servidor)

Cada conexão é atendida em uma thread própria, com um thread receptor
separado do `input()` do operador — assim um PING é respondido mesmo
enquanto o operador está digitando a resposta de um chat.
"""

import socket
import sys
import threading

from protocol import (
    DELIMITADOR,
    TIPO_BYE,
    TIPO_ECHO,
    TIPO_ERROR,
    TIPO_EXIT,
    TIPO_HELLO,
    TIPO_MSG,
    TIPO_PING,
    TIPO_PONG,
    TIPOS_CLIENTE_SERVIDOR,
    criar_mensagem,
    receber_mensagem,
)

HOST = "0.0.0.0"  # escuta em todas as interfaces de rede
IDLE_TIMEOUT = 60  # segundos sem atividade antes de descartar um cliente ocioso

try:
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
except ValueError:
    print(f"[Erro] Porta inválida: {sys.argv[1]!r}. Use um número (ex.: 5000).")
    sys.exit(1)


def atender_cliente(conn: socket.socket, address) -> None:
    """Atende um cliente conectado, em uma thread própria.

    Usa um thread receptor (que faz recv e responde PING/ECHO/EXIT
    automaticamente) separado do thread que lê o `input()` do operador.
    Isso evita que o `input()` bloqueante impeça o servidor de responder
    a keep-alives ou de detectar a desconexão do cliente.
    """
    ip, porta = address[0], address[1]
    print(f"\n[+] Cliente conectado: {ip}:{porta}")
    print(f"[i] Protocolo: <TIPO>:<DADOS>{DELIMITADOR!r}\n")

    buffer = bytearray()  # acumulador de bytes para o framing (recv parcial)
    enviar_lock = threading.Lock()  # serializa sendall entre os dois threads
    parar = threading.Event()       # sinaliza que a sessão deve encerrar
    responder = threading.Event()   # sinaliza que há um HELLO aguardando o operador

    def enviar(msg: bytes) -> None:
        with enviar_lock:
            conn.sendall(msg)

    def receptor() -> None:
        """Lê o socket e responde automaticamente a PING/ECHO/EXIT."""
        while not parar.is_set():
            try:
                resultado = receber_mensagem(conn, buffer)
            except socket.timeout:
                # Ocioso: não há dados, mas a conexão pode continuar viva.
                continue
            except ValueError as erro:
                # Mensagem malformada: avisa o cliente e continua no loop
                print(f"[!] Mensagem inválida recebida: {erro}")
                enviar(criar_mensagem(TIPO_ERROR, f"formato_invalido: {erro}"))
                continue
            except UnicodeDecodeError:
                print("[!] Recebido dado com encoding inválido.")
                enviar(criar_mensagem(TIPO_ERROR, "encoding_invalido"))
                continue
            except ConnectionResetError:
                print("\n[-] Conexão resetada pelo cliente (RST).")
                parar.set()
                responder.set()  # destrava o operador
                break

            if resultado is None:
                # recv devolveu b'' => cliente enviou FIN (desconectou)
                print("\n[-] O cliente encerrou a conexão.")
                parar.set()
                responder.set()  # destrava o operador
                break

            tipo, dados = resultado
            print(f" Cliente [{tipo}]: {dados}")

            # Valida a direção: o servidor só aceita tipos C -> S
            if tipo not in TIPOS_CLIENTE_SERVIDOR:
                enviar(criar_mensagem(TIPO_ERROR, f"direcao_invalida: {tipo}"))
                continue

            if tipo == TIPO_HELLO:
                # Precisa da resposta do operador: sinaliza o thread principal
                responder.set()
            elif tipo == TIPO_ECHO:
                enviar(criar_mensagem(TIPO_ECHO, dados))
            elif tipo == TIPO_PING:
                enviar(criar_mensagem(TIPO_PONG, ""))
            elif tipo == TIPO_EXIT:
                enviar(criar_mensagem(TIPO_BYE, "sessao_encerrada"))
                print("[*] Cliente solicitou o encerramento da sessão.")
                parar.set()
                responder.set()  # destrava o operador
                break

    conn.settimeout(IDLE_TIMEOUT)  # detecta cliente que "some" sem FIN
    thread_receptor = threading.Thread(target=receptor, daemon=True)
    thread_receptor.start()

    try:
        # Thread principal: espera um HELLO (via `responder`) e lê a resposta
        # do operador, enviando MSG. Desacoplado do recv.
        while not parar.is_set():
            responder.wait()
            responder.clear()
            if parar.is_set():
                break
            try:
                texto = input(" Servidor: ")
            except EOFError:
                # Entrada padrão fechada (ex.: pipe encerrado)
                enviar(criar_mensagem(TIPO_BYE, "servidor_encerrando"))
                break
            enviar(criar_mensagem(TIPO_MSG, texto))
    except (BrokenPipeError, ConnectionError) as erro:
        print(f"\n[-] Conexão perdida com o cliente: {erro}")
    finally:
        parar.set()
        responder.set()
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()
        print("[*] Conexão com o cliente fechada.")


def main() -> None:
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

        # backlog maior que 1 para aceitar conexões pendentes enquanto atende
        server.listen(5)

        print("=" * 48)
        print("        SERVIDOR TCP INICIADO (protocolo próprio)")
        print(f"  Endereço de escuta : {HOST}:{PORT}")
        print("  Aguardando conexões de clientes...")
        print("  (Pressione Ctrl+C para encerrar o servidor)")
        print("=" * 48)

        # Loop de accept(): atende cliente após cliente sem morrer ao final
        while True:
            try:
                conn, address = server.accept()
            except KeyboardInterrupt:
                raise
            # Cada cliente é atendido em uma thread própria
            threading.Thread(
                target=atender_cliente, args=(conn, address), daemon=True
            ).start()

    except KeyboardInterrupt:
        print("\n\n[!] Servidor finalizado pelo usuário.")
    finally:
        server.close()
        print("[*] Socket do servidor finalizado com sucesso.")


if __name__ == "__main__":
    main()
