# Sistema de Chat TCP Cliente-Servidor com Sockets

Este projeto implementa uma aplicação cliente-servidor minimalista utilizando sockets **TCP (Transmission Control Protocol)** em Python puro (sem bibliotecas externas).

Desenvolvido para fins didáticos na disciplina de **Fundamentos em Redes de Computadores**.

---

## 📐 Arquitetura e Fluxo de Comunicação

O TCP é um protocolo orientado à conexão. O servidor inicia escutando em uma porta definida, o cliente realiza a conexão via handshake, e ambos passam a trocar mensagens sequenciais de forma confiável.

```text
┌──────────────┐        TCP Socket        ┌──────────────┐
│    Cliente   │ ───────────────────────► │    Servidor  │
│              │ ◄─────────────────────── │              │
└──────────────┘                          └──────────────┘
      envia                                      recebe
    mensagem                                   mensagem
```

### Fluxo de Chamadas dos Sockets

```text
             SERVIDOR                                  CLIENTE
                │                                         │
        socket.socket()                           socket.socket()
                │                                         │
             bind()                                       │
                │                                         │
            listen()                                      │
                │                                         │
            accept() ◄─── Three-Way Handshake ────────── connect()
                │                                         │
                │ ◄─────────── sendall() / recv() ─────── │
                │                                         │
                │ ──────────── sendall() / recv() ──────► │
                │                                         │
             close() ◄──────── Fechamento FIN/ACK ─────── close()
```

---

## 🔍 Dicionário de Primitivas de Sockets

Tudo o que você precisa saber para explicar o código passo a passo:

| Primitiva | Camada / Descrição | O que faz no código |
| :--- | :--- | :--- |
| `socket.socket(AF_INET, SOCK_STREAM)` | Camada de Transporte | Cria o descritor do socket. `AF_INET` indica IPv4 e `SOCK_STREAM` indica o protocolo TCP (confiável, orientado a fluxo de bytes). |
| `setsockopt(..., SO_REUSEADDR, 1)` | Configuração de Socket | Permite reutilizar o endereço e a porta imediatamente caso o servidor seja reiniciado, evitando o erro `Address already in use`. |
| `server.bind((HOST, PORT))` | Camada de Rede / Transporte | Associa o socket a uma interface de rede (`HOST`) e porta local (`PORT`). Usamos `"0.0.0.0"` para ouvir em todas as interfaces. |
| `server.listen(backlog)` | Estado do Socket | Coloca o socket em modo passivo (escuta), definindo quantas conexões pendentes podem aguardar na fila (`backlog`). |
| `server.accept()` | Estabelecimento de Conexão | Bloqueia a execução até que um cliente se conecte. Retorna uma tupla contendo um **novo socket dedicado à conexão** (`conn`) e a tupla de endereço do cliente `(ip, porta)`. |
| `client.connect((HOST, PORT))` | Estabelecimento de Conexão | Realiza o *Three-Way Handshake* TCP com o servidor no endereço e porta indicados. |
| `conn.sendall(dados)` / `send()` | Transferência de Dados | Envia os bytes (codificados em UTF-8) pelo fluxo de rede TCP. |
| `conn.recv(1024)` | Transferência de Dados | Bloqueia até receber dados pelo socket (até 1024 bytes). Retorna `b""` (vazio) quando a outra ponta encerra a conexão de forma limpa. |
| `socket.close()` | Finalização | Envia os pacotes de finalização (`FIN`/`ACK`) e libera as portas e recursos de rede do sistema operacional. |

---

## 🚀 Como Executar

### Pré-requisitos
- Python 3.8 ou superior instalado em ambas as máquinas/terminais.

---

### Opção 1: Testando Localmente (Mesmo Computador)

Abra dois terminais diferentes:

**1. No Terminal 1 (Servidor):**
```bash
python3 server.py
```
*(O servidor ficará aguardando conexões na porta 5000)*

**2. No Terminal 2 (Cliente):**
```bash
python3 client.py
```
*(Conecta automaticamente em `127.0.0.1:5000`)*

---

### Opção 2: Testando entre Dois Computadores (Rede Local / Wi-Fi)

```text
NOTEBOOK A (Servidor)                   NOTEBOOK B (Cliente)
IP: 192.168.1.15                        IP: 192.168.1.20
   server.py  ◄────── Wi-Fi / LAN ──────►  client.py 192.168.1.15
   Porta 5000                              Porta 5000
```

1. **Descubra o IP local da máquina Servidor:**
   - **Linux:** execute `ip addr` ou `hostname -I` (procure o IP da interface `wlan0` ou `eth0`, ex: `192.168.1.15`).
   - **Windows:** execute `ipconfig` no CMD (procure por `Endereço IPv4`).

2. **No Computador A (Servidor):**
   ```bash
   python3 server.py
   ```
   *Nota: Certifique-se de que o firewall do sistema permite conexões de entrada na porta 5000.*

3. **No Computador B (Cliente):**
   Passe o IP do servidor como argumento:
   ```bash
   python3 client.py 192.168.1.15
   ```
   *(Substitua `192.168.1.15` pelo IP real da máquina A)*

---

## 💡 Por que TCP e não UDP?

1. **Orientado à Conexão:** Garante que ambos os lados estão prontos e cientes antes de trocar dados (*Three-Way Handshake*).
2. **Entrega Confiável e Ordenada:** O próprio protocolo TCP trata confirmação de recebimento (ACK), retransmissão de pacotes perdidos e montagem das mensagens na ordem correta.
3. **Detecção de Desconexão:** Se o cliente fechar o terminal, o método `recv()` do servidor recebe `b""` imediatamente, permitindo que a aplicação trate a saída de forma limpa.
