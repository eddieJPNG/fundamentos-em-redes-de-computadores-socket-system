import socket
import sys

# Permite passar o IP do servidor como argumento (ex: python client.py 192.168.1.15)
HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    print(f"[*] Conectando ao servidor em {HOST}:{PORT}...")
    client.connect((HOST, PORT))
    print("[+] Conectado ao servidor!")
    print("Digite suas mensagens abaixo. Digite '/sair' ou Ctrl+C para encerrar.\n")

    while True:
        try:
            message = input("Você: ")
        except EOFError:
            break

        if not message.strip():
            continue

        if message.strip().lower() == "/sair":
            print("[*] Encerrando a conexão...")
            break

        client.sendall(message.encode("utf-8"))

        response = client.recv(1024)
        if not response:
            print("\n[-] O servidor encerrou a conexão.")
            break

        print(f"Servidor: {response.decode('utf-8')}")

except ConnectionRefusedError:
    print(f"\n[Erro] Não foi possível conectar a {HOST}:{PORT}.")
    print("Verifique se o servidor está em execução e se o IP/porta estão corretos.")
except KeyboardInterrupt:
    print("\n\n[!] Desconectado pelo usuário.")
finally:
    client.close()
    print("[*] Conexão do cliente encerrada.")
