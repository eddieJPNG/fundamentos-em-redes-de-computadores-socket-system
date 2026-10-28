# Sistema de Chat TCP Cliente-Servidor com Sockets e Protocolo Próprio

Aplicação cliente-servidor que realiza **comunicação entre processos** por meio de **sockets TCP** em Python puro (sem bibliotecas externas), utilizando um **protocolo de aplicação próprio** para estruturar as mensagens.

Desenvolvido para a atividade avaliativa da disciplina de **Fundamentos de Redes de Computadores**.

---

## 👥 Integrantes

| Nome | Matrícula |
| :--- | :--- |
| _— Edson Rocha da Silva —_ | _— 2025012382 —_ |
| _— Matheus Soares Diniz Couto  —_ | _— 2025027545 —_ |
| _— David de Carvalho Santos  —_ | _— 2025012373 —_ |



---

## 1. Problema que a aplicação resolve

Dois processos executando em **máquinas distintas** (ou na mesma máquina, para fins didáticos) precisam **conversar entre si**, de forma **confiável e ordenada**. A aplicação resolve o problema de **transmissão de mensagens de texto bidirecional** entre um cliente e um servidor, demonstrando na prática como a **camada de aplicação** utiliza a **camada de transporte (TCP)** e a **primitiva de sockets** para se comunicar através da rede.

> **Nota sobre "tempo real":** os comandos `PING`/`ECHO`/`EXIT` são respondidos **automaticamente** por um thread receptor, mesmo enquanto o operador digita a resposta de um chat. Já as mensagens de chat (`HELLO` → `MSG`) aguardam a digitação do operador no servidor — o que é o comportamento esperado de um chat operado por humano, e não uma limitação do transporte.

---

## 2. Processos envolvidos na comunicação

| Processo | Arquivo | Papel |
| :--- | :--- | :--- |
| **Servidor** | `server.py` | Fica em modo passivo, escutando na porta `5000` em `0.0.0.0` (todas as interfaces). Aceita conexões em um loop (`accept()`) e atende cada cliente em uma thread própria. |
| **Cliente** | `client.py` | Inicia a conexão (modo ativo) com o IP e porta do servidor, envia mensagens e imprime as respostas. |
| **Protocolo** | `protocol.py` | Módulo compartilhado com a definição do **protocolo de aplicação** (criação, validação e leitura das mensagens). |

---

## 3. Arquitetura e fluxo da comunicação

```text
┌────────────────────┐                                    ┌────────────────────┐
│      CLIENTE       │                                    │      SERVIDOR      │
│   (processo ativo) │                                    │  (processo passivo)│
│   client.py        │                                    │    server.py       │
│  IP: 192.168.1.20  │ ────────── TCP / porta 5000 ─────► │  IP: 192.168.1.15  │
│                    │ ◄───────────────────────────────── │  0.0.0.0:5000      │
└────────────────────┘        mensagens <TIPO>:<DADOS>    └────────────────────┘
```

### Fluxo de chamadas dos sockets

```text
             SERVIDOR                                  CLIENTE
                │                                         │
        socket.socket()                           socket.socket()
                │                                         │
             bind()                                       │
                │                                         │
            listen()                                      │
                │                                         │
                │            Three-Way Handshake          │
                │         (SYN / SYN-ACK / ACK)           │
                │        ◄──── feito pelo kernel ────►    │
                │            ANTES do accept()            │
                │                                         │
            accept()                                      │
        (retorna um socket                                 │
         já conectado)                                    │
                │                                         │
                │ ◄─────────── sendall() / recv() ─────── │
                │                                         │
                │ ──────────── sendall() / recv() ──────► │
                │                                         │
             close() ◄──── Fechamento FIN/ACK ────────► close()
                │          (4 segmentos: FIN+ACK de       │
                │           cada lado, em duas fases)      │
```

> **Nota:** o *Three-Way Handshake* é realizado pelo kernel TCP e **já termina antes** de `accept()` retornar — `accept()` apenas "desenfileira" uma conexão que o kernel já estabeleceu. Por isso, um segundo cliente consegue completar o handshake (o kernel aceita no *backlog*) mesmo antes de o programa chamar `accept()` novamente.

---

## 4. Protocolo de transporte: **TCP**

`socket.socket(AF_INET, socket.SOCK_STREAM)` → **TCP** (orientado à conexão).

### 5. Justificativa da escolha do TCP

1. **Orientado à conexão:** garante que ambos os lados estão prontos e cientes antes de trocar dados (*Three-Way Handshake*). Em um chat, não faz sentido perder mensagens.
2. **Entrega confiável e ordenada:** o próprio TCP trata confirmação de recebimento (ACK), retransmissão de pacotes perdidos e reordenação. A aplicação não precisa se preocupar com perdas.
3. **Detecção de desconexão:** se o cliente fechar o terminal, o `recv()` do servidor recebe `b""` (ou levanta `ConnectionResetError`), permitindo tratar a saída de forma limpa.
4. **Fluxo de bytes:** o TCP entrega exatamente a sequência de bytes enviada — ideal para um protocolo de texto delimitado por `\n`.

### 6. O que aconteceria se usássemos **UDP**?

Se o transporte fosse **UDP** (`SOCK_DGRAM`, sem conexão):
- **Sem handshake:** não haveria fase de conexão; o cliente poderia "enviar para o vazio" sem saber se o servidor existe.
- **Sem confiabilidade:** mensagens poderiam ser **perdidas, duplicadas ou chegar fora de ordem** — em um chat, isso resultaria em falas trocadas ou sumidas.
- **Sem detecção de desconexão automática:** o servidor não saberia que o cliente saiu (não há FIN); precisaria de *timeouts* ou *keep-alives* próprios (ex.: o comando `PING`/`PONG` implementado aqui).
- **Datagramas independentes:** cada `recvfrom` traz um datagrama inteiro, então o *framing* por `\n` seria menos necessário — mas a aplicação teria que **implementar por conta própria** confiabilidade, ordenação e controle de fluxo.

> Conclusão: para um chat onde **importa que todas as mensagens cheguem intactas e na ordem**, o TCP é a escolha natural. O UDP seria adequado para aplicações com tolerância a perda e requisito de baixa latência (ex.: streaming de vídeo, jogos em tempo real, DNS).

---

## 7. Protocolo da aplicação (protocolo próprio)

As mensagens seguem o formato textual, delimitado por linha:

```text
<TIPO>:<DADOS>\n
```

- `<TIPO>` — identificador do tipo da mensagem (ex.: `HELLO`, `MSG`).
- `<DADOS>` — conteúdo da mensagem (pode conter espaços, acentos e até o caractere `:` — o parsing separa apenas no **primeiro** `:`).
- `\n` — **delimitador de mensagem** (*framing*). Como o TCP é um fluxo de bytes, o receptor acumula dados em um buffer até encontrar o `\n`, garantindo que mensagens grandes ou fragmentadas em vários segmentos sejam lidas corretamente.

Este protocolo é implementado no módulo **`protocol.py`**, compartilhado por cliente e servidor.

---

## 8. Mensagens utilizadas

| Tipo | Direção | Dados | Significado |
| :--- | :--- | :--- | :--- |
| `HELLO` | Cliente → Servidor | texto da mensagem | Mensagem de chat do usuário |
| `ECHO` | Cliente → Servidor | texto a ecoar | Solicita eco (teste de ida e volta) |
| `ECHO` | Servidor → Cliente | mesmos dados recebidos | Resposta ao eco |
| `PING` | Cliente → Servidor | (vazio) | *Keep-alive* / teste de conectividade |
| `PONG` | Servidor → Cliente | (vazio) | Resposta ao `PING` |
| `MSG` | Servidor → Cliente | texto de resposta | Resposta do operador a uma mensagem de chat |
| `EXIT` | Cliente → Servidor | motivo (ex.: `bye`) | Cliente deseja encerrar a sessão |
| `BYE` | Servidor → Cliente | motivo (ex.: `sessao_encerrada`) | Confirmação de encerramento / aviso de desligamento |
| `ERROR` | Servidor → Cliente | motivo do erro | Erro de protocolo (ex.: `formato_invalido`) |

> O `ACK` genérico foi dividido em dois tipos com papéis claros: `MSG` (resposta de chat) e `BYE` (encerramento). Isso evita ambiguidade entre "resposta do operador", "confirmação de EXIT" e "aviso de shutdown" — que antes eram todos `ACK`.

### Exemplos de mensagens (formato que trafega na rede)

```text
HELLO:Olá, tudo bem?
MSG:Oi! Tudo ótimo.
ECHO:ecoa isto
ECHO:ecoa isto
PING:
PONG:
EXIT:bye
BYE:sessao_encerrada
ERROR:formato_invalido: Mensagem sem separador ':' ...
```

> **Atenção:** todo tipo vai seguido de `:`, mesmo com os dados vazios — `PING:` e `PONG:` (não `PING`/`PONG`). O cliente `/ping` envia exatamente `PING:\n`.

### Comandos digitados pelo usuário (lado do cliente)

| Entrada | Mensagem enviada |
| :--- | :--- |
| _(texto livre)_ | `HELLO:<texto>` |
| `/eco <texto>` | `ECHO:<texto>` |
| `/ping` | `PING:` |
| `/sair` | `EXIT:bye`, lê o `BYE` do servidor e só então encerra (FIN limpo) |
| `/ajuda` | _(não envia nada — apenas mostra a ajuda local)_ |

---

## 9 e 10. Situações de erro e como são tratadas

### Tratadas pelo **Cliente** (`client.py`)

| Situação de erro | Exceção / Detecção | Tratamento |
| :--- | :--- | :--- |
| Servidor não está no ar | `ConnectionRefusedError` | Mensagem orientando a verificar o servidor e a porta |
| IP/host inexistente | `socket.gaierror` | Mensagem de "endereço inválido" com sugestão de IP |
| Servidor não responde a tempo | `socket.settimeout(10)` **antes do `connect`** + `except (socket.timeout, TimeoutError)` | Mensagem de "tempo esgotado ao conectar" (o timeout cobre só a conexão; após conectar a leitura é bloqueante) |
| Servidor reinicia a conexão | `ConnectionResetError` | Mensagem de "conexão resetada (RST)" |
| Envio para conexão já fechada | `BrokenPipeError` | Mensagem de "conexão perdida" e encerra o loop |
| Porta informada não é numérica | `ValueError` no `int()` | Mensagem de "porta inválida" e `sys.exit(1)` |
| Mensagem malformada do servidor | `ValueError` no `parsear` | Avisa o usuário e continua no loop |
| Dados corrompidos na rede | `UnicodeDecodeError` | Avisa "encoding inválido" |
| Entrada padrão fechada (Ctrl+D / pipe) | `EOFError` | Encerra de forma limpa |
| Interrupção do usuário (Ctrl+C) | `KeyboardInterrupt` | Mensagem de desconexão e `close()` no `finally` |

### Tratadas pelo **Servidor** (`server.py`)

| Situação de erro | Exceção / Detecção | Tratamento |
| :--- | :--- | :--- |
| Porta já em uso / sem permissão | `OSError` no `bind` | Mensagem clara e `sys.exit(1)` |
| Mensagem do cliente malformada | `ValueError` no `parsear` | Responde `ERROR:formato_invalido` e **continua no ar** (não derruba o servidor) |
| Encoding inválido | `UnicodeDecodeError` | Responde `ERROR:encoding_invalido` e continua |
| Tipo na direção errada (ex.: `ACK` vindo do cliente) | `tipo not in TIPOS_CLIENTE_SERVIDOR` | Responde `ERROR:direcao_invalida:<tipo>` e continua |
| Cliente inativo (sem FIN, sem dados) | `conn.settimeout(60)` + `socket.timeout` | Fecha a sessão ociosa e volta a aceitar novos clientes |
| Cliente reinicia (RST) | `ConnectionResetError` | Mensagem e encerramento limpo |
| Cliente some no meio da resposta | `BrokenPipeError` / `ConnectionError` | Mensagem e encerramento limpo |
| Cliente envia `FIN` (desconecta) | `recv` → `b""` → `receber_mensagem` retorna `None` | Detecta e encerra a sessão |
| Porta reiniciada rapidamente | `SO_REUSEADDR = 1` | Evita o erro *"Address already in use"* |
| Entrada padrão do servidor fechada | `EOFError` no `input` | Envia `BYE:servidor_encerrando` e encerra a sessão |
| Interrupção do usuário (Ctrl+C) | `KeyboardInterrupt` | Encerramento limpo (`finally` fecha sockets) |

---

## 📦 Dicionário de primitivas de sockets

| Primitiva | O que faz no código |
| :--- | :--- |
| `socket.socket(AF_INET, SOCK_STREAM)` | Cria o descritor do socket TCP (IPv4). |
| `setsockopt(..., SO_REUSEADDR, 1)` | Permite reutilizar a porta imediatamente após reinício do servidor. |
| `bind((HOST, PORT))` | Associa o socket à interface (`0.0.0.0` = todas) e porta local. |
| `listen(backlog)` | Coloca o socket em modo passivo (escuta), com fila de conexões pendentes. |
| `accept()` | Bloqueia até um cliente conectar; retorna um **novo socket dedicado** (`conn`) e o endereço `(ip, porta)`. |
| `connect((HOST, PORT))` | Realiza o *Three-Way Handshake* TCP com o servidor. |
| `sendall(dados)` | Envia todos os bytes (UTF-8) pelo fluxo TCP, sem cortes. |
| `recv(4096)` | Bloqueia até receber dados; `b""` significa que a outra ponta enviou `FIN`. |
| `settimeout(seg)` | Limita o tempo de espera do cliente **na fase de conexão** (`connect`). Após conectar, a leitura do cliente é bloqueante (`settimeout(None)`); o servidor aplica um timeout de ociosidade (`IDLE_TIMEOUT`) por conexão. |
| `close()` | Envia `FIN`/`ACK` e libera os recursos de rede. |

---

## 🚀 Como executar

### Pré-requisitos
- Python 3.8 ou superior em ambos os terminais/máquinas.

### Opção 1 — Testando localmente (mesmo computador)

**Terminal 1 (servidor):**
```bash
python3 server.py
```
*(escuta em `0.0.0.0:5000`)*

**Terminal 2 (cliente):**
```bash
python3 client.py
```
*(conecta automaticamente em `127.0.0.1:5000`)*

### Opção 2 — Testando entre dois computadores (rede local / Wi-Fi)

```text
NOTEBOOK A (Servidor)                   NOTEBOOK B (Cliente)
IP: 192.168.1.15                        IP: 192.168.1.20
   server.py  ◄────── Wi-Fi / LAN ──────►  client.py 192.168.1.15
   Porta 5000                              Porta 5000
```

1. **Descubra o IP da máquina servidora:**
   - **Linux:** `ip addr` ou `hostname -I`
   - **Windows:** `ipconfig` (procure *IPv4 Address*)
2. **Máquina A (servidor):** `python3 server.py` (libere a porta 5000 no firewall).
3. **Máquina B (cliente):** `python3 client.py 192.168.1.15` (substitua pelo IP real).

### Endereços padrão

| Item | Valor |
| :--- | :--- |
| IP do servidor (escuta) | `0.0.0.0` (todas as interfaces) |
| IP do cliente (padrão) | `127.0.0.1` (loopback) |
| Porta | `5000` (configurável por argumento) |

---

## 🔬 Análise de tráfego com Wireshark

Para gerar a evidência de captura de tráfego (entrega da atividade):

1. Inicie o **servidor** na máquina A e o **cliente** na máquina B (ou ambos localmente).
2. No Wireshark, selecione a interface de rede correta (ou `Loopback` para testes locais) e inicie a captura.
3. Aplique o filtro para isolar o tráfego da aplicação:
   ```text
   tcp.port == 5000
   ```
4. Realize alguns exchanges (mensagem de chat, `/ping`, `/eco`).
5. Pare a captura e **salve o arquivo `.pcapng`**.

### O que evidenciar na captura

- **Three-Way Handshake:** pacotes `SYN` → `SYN, ACK` → `ACK` no início da conexão (feitos pelo kernel, antes de `accept()` retornar).
- **Segmentos de dados:** os payloads `HELLO:...`, `MSG:...`, `PING:`, `PONG:` visíveis na coluna *Info* / *Data* de cada segmento TCP.
- **ACKs de transporte:** confirmações de recebimento do próprio TCP (números de sequência/acknowledgment).
- **Fechamento:** a sequência de `FIN`/`ACK` ao final. Como o servidor fecha primeiro (ao receber `EXIT`), o lado do **servidor** fica em `TIME_WAIT` — é por isso que o `SO_REUSEADDR` do servidor é útil. O encerramento limpo são **4 segmentos** (FIN+ACK de cada lado, em duas fases).

> Dica: use `Analyze → Follow → TCP Stream` no Wireshark para visualizar a conversa completa em texto, mostrando claramente o protocolo `<TIPO>:<DADOS>` trafegando.

> **Nota de sincronismo:** o protocolo é *lockstep* (1 envio ↔ 1 resposta). Ao usar `/ping` ou `/eco`, o cliente lê a resposta imediatamente; ao usar `/sair`, ele lê o `BYE` **antes** de fechar. Isso garante um fechamento `FIN` limpo em vez de `RST` (que ocorreria se o socket fechasse com dados ainda não lidos no buffer).

**Captura anexa:** _(inserir print/screenshot ou arquivo `.pcapng` da captura)_

---

## 🗂 Estrutura do projeto

```text
.
├── server.py     # Processo servidor (escuta, aceita conexão, responde)
├── client.py     # Processo cliente (conecta, envia, recebe)
├── protocol.py   # Protocolo de aplicação próprio (criar/parsear/receber)
├── README.md     # Esta documentação
├── LICENSE
└── .gitignore
```

---

## 💡 Conclusão

Este projeto demonstra, na prática, como uma **aplicação da camada de aplicação** utiliza a **primitiva de sockets** e o **TCP** para realizar comunicação confiável entre processos em rede. A adoção de um **protocolo de aplicação próprio** (`<TIPO>:<DADOS>\n`) com *framing* por delimitador ilustra como o TCP — um protocolo de **fluxo de bytes** — exige que a aplicação trate o contorno das mensagens, enquanto a confiabilidade e a ordenação ficam por conta do transporte.
