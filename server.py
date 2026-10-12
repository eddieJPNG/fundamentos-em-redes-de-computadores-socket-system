import socket
import sys

HOST = "0.0.0.0"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Evita erro de 'porta já em uso' ao reiniciar rápido
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    server.bind((HOST, PORT))
    server.listen(1)

    print("=" * 45)
    print("          SERVIDOR TCP INICIADO")
    print(f"  Porta de escuta: {PORT}")
    print("  Aguardando conexão de um cliente...")
    print("  (Pressione Ctrl+C para encerrar o servidor)")
    print("=" * 45)

    conn, address = server.accept()
    print(f"\n[+] Cliente conectado: {address[0]}:{address[1]}\n")

    try:
        while True:
            data = conn.recv(1024)
            # Se não vier dados, o cliente desconectou
            if not data:
                print("\n[-] O cliente encerrou a conexão.")
                break

            message = data.decode("utf-8")
            print(f"Cliente: {message}")

            try:
                response = input("Servidor: ")
            except EOFError:
                break

            conn.sendall(response.encode("utf-8"))

    except ConnectionResetError:
        print("\n[-] Conexão resetada pelo cliente.")
    finally:
        conn.close()
        print("[*] Conexão com o cliente fechada.")

except KeyboardInterrupt:
    print("\n\n[!] Servidor finalizado pelo usuário.")
finally:
    server.close()
    print("[*] Socket do servidor finalizado com sucesso.")
