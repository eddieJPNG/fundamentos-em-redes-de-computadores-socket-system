# 📚 GUIA DE ESTUDO — Linha por Linha
## Sistema de Chat TCP com Protocolo de Aplicação Próprio

> **Objetivo deste documento:** explicar **cada linha de código** dos três arquivos
> (`protocol.py`, `server.py`, `client.py`) de forma didática, ligando cada trecho
> aos **conceitos de Redes de Computadores** cobrados na atividade.
>
> **Como usar:** leia um bloco de código, depois a tabela/explicação correspondente.
> Ao final há um resumo de conceitos e perguntas de fixação (estilo flashcard).

---

## 🗺️ VISÃO GERAL DO SISTEMA (antes de ler o código)

O sistema são **dois processos** que conversam por rede:

```text
   CLIENTE (client.py)                     SERVIDOR (server.py)
   inicia a conexão                        aceita a conexão
   IP: 192.168.1.20                        IP: 0.0.0.0 (escuta em tudo)
        │                                        ▲
        │  1) SYN ─────────────────────────────► │
        │  2) ◄───────────────────── SYN,ACK     │  ← Three-Way Handshake (TCP)
        │  3) ACK ─────────────────────────────► │
        │                                        │
        │  4) HELLO:Olá ───────────────────────► │  ← dados (protocolo próprio)
        │  5) ◄────────────────────── ACK:Oi!    │
        │                                        │
        │  9) FIN ─────────────────────────────► │  ← fechamento (TCP)
        │ 10) ◄──────────────── FIN,ACK / ACK    │
```

**Três arquivos, três papéis:**

| Arquivo | Papel | "Ator" |
| :--- | :--- | :--- |
| `protocol.py` | Define o **formato das mensagens** (o "idioma" falado por ambos) | Biblioteca compartilhada |
| `server.py` | Escuta, aceita 1 cliente e responde | Processo passivo |
| `client.py` | Conecta, envia comandos e imprime respostas | Processo ativo |

**Ideia central do TCP que você DEVE decorar:**
> O TCP entrega um **fluxo de bytes** (não "pacotes de mensagens").
> Uma `recv()` **não** retorna necessariamente 1 mensagem inteira —
> pode vir meio, uma e meia, ou várias. Por isso existe o `protocol.py`
> com **framing** (delimitador `\n`) e um **buffer acumulador**.

---

# PARTE 1 — `protocol.py` (o "idioma" do sistema)

> Arquivo que **não** se conecta à rede. Ele só **monta, valida e lê** mensagens.
> É importado pelos outros dois arquivos (`from protocol import ...`).

## 1.1 — Cabeçalho / Docstring (linhas 1 a 25)

```python
"""
Protocolo de Aplicação — Chat TCP Cliente-Servidor
==================================================

Formato de cada mensagem (uma por linha):

    <TIPO>:<DADOS>\n
...
"""
```

**O que é:** um *docstring* (string tripla `"""`). É só documentação — o Python
ignora na execução. Serve para o programador (e a equipe) entender o arquivo.

**Conceito-chave:** o **protocolo da aplicação**. Um protocolo de aplicação define:
- o **formato** das mensagens (`<TIPO>:<DADOS>\n`)
- a **semântica** (o que cada tipo significa)
- as **regras** (quem pode enviar o quê)

> 📖 Analogia: o TCP é o "correio" (transporta cartas confiavelmente).
> O `protocol.py` é o "formato da carta" (para o remetente e destinatário
> entenderem o conteúdo).

## 1.2 — Constantes (linhas 31 a 47)

```python
SEPARADOR = ":"      # separa <TIPO> dos <DADOS>
DELIMITADOR = "\n"   # delimita o fim de uma mensagem no fluxo de bytes

MAX_DADOS = 4096     # limite dos dados (payload) de uma mensagem
```

| Linha | Constante | Papel didático |
| :--- | :--- | :--- |
| 31 | `SEPARADOR = ":"` | Divide a mensagem em "cabeçalho" (tipo) e "corpo" (dados) |
| 32 | `DELIMITADOR = "\n"` | **Framing**: sinaliza onde uma mensagem termina no fluxo de bytes contínuo |
| 34 | `MAX_DADOS = 4096` | Proteção: limita o tamanho do *payload* (não confundir com o buffer do `recv`) |

> ⚠️ **Framing** é um dos conceitos mais importantes. Como o TCP não "enxerga"
> mensagens (só bytes), o `\n` marca a fronteira. É o mesmo princípio de
> protocolos reais como HTTP (`\r\n\r\n`) e o SMTP.

```python
TIPO_HELLO = "HELLO"  # C -> S : mensagem de chat
TIPO_ECHO = "ECHO"    # C -> S : solicita eco ; S -> C : eco retornado
TIPO_PING = "PING"    # C -> S : keep-alive
TIPO_PONG = "PONG"    # S -> C : resposta ao PING
TIPO_ACK = "ACK"      # S -> C : confirmação
TIPO_EXIT = "EXIT"    # C -> S : encerrar sessão
TIPO_ERROR = "ERROR"  # S -> C : erro de protocolo
```

**Os 7 tipos de mensagem.** Decorar a direção (C→S ou S→C) é essencial:

| Tipo | Direção | Quando é usada |
| :--- | :--- | :--- |
| `HELLO` | Cliente → Servidor | Usuário digita uma frase de chat |
| `ECHO` | Cliente → Servidor (e volta) | Teste: servidor devolve os MESMOS dados |
| `PING` | Cliente → Servidor | Keep-alive / "você ainda está aí?" |
| `PONG` | Servidor → Cliente | Resposta ao `PING` |
| `ACK` | Servidor → Cliente | Confirmação / resposta de chat |
| `EXIT` | Cliente → Servidor | "Vou sair, tchau" |
| `ERROR` | Servidor → Cliente | Algo deu errado no protocolo |

```python
TIPOS_CLIENTE_SERVIDOR = {TIPO_HELLO, TIPO_ECHO, TIPO_PING, TIPO_EXIT}
TIPOS_SERVIDOR_CLIENTE = {TIPO_ACK, TIPO_PONG, TIPO_ECHO, TIPO_ERROR}
TIPOS_VALIDOS = TIPOS_CLIENTE_SERVIDOR | TIPOS_SERVIDOR_CLIENTE
```

- **Conjuntos (sets)**: estruturas de dados sem repetição, de busca rápida.
- `|` é a **união** de conjuntos → `TIPOS_VALIDOS` contém todos os tipos.
- `TIPO_ECHO` aparece nos DOIS conjuntos (vai e volta) — é o único bidirecional.

> 💡 **Por que usar constantes (`TIPO_ACK = "ACK"`) e não strings soltas?**
> Porque evita "erro de digitação fantasma". Se você digitar `"ACk"`, o programa
> falha cedo e de forma clara, em vez de quebrar silenciosamente em produção.

## 1.3 — `criar_mensagem()` (linhas 54 a 72) — SERIALIZAÇÃO

```python
def criar_mensagem(tipo: str, dados: str = "") -> bytes:
```
**Assinatura:** recebe `tipo` (obrigatório) e `dados` (opcional, padrão `""`).
Retorna **`bytes`** (pronto para `sendall`), não `str`.

```python
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo de mensagem inválido: {tipo!r}")
```
**Validação 1:** se o tipo não existe no protocolo, **levanta exceção** (`raise`).
Assim, um erro de programação é pego NO MOMENTO da montagem, não na rede.

```python
    if len(dados) > MAX_DADOS:
        raise ValueError(...)
```
**Validação 2:** limita o tamanho do payload.

```python
    linha = f"{tipo}{SEPARADOR}{dados.replace(chr(10), ' ')}{DELIMITADOR}"
    return linha.encode("utf-8")
```
- `dados.replace(chr(10), ' ')`: `chr(10)` é o código do `\n`. Troca eventuais
  quebras de linha dos dados por espaço — **para não quebrar o framing**.
- `f"{...}"`: monta a string final, ex.: `"HELLO:Olá\n"`.
- `.encode("utf-8")`: **converte texto → bytes**. A rede só transporta bytes.
  - `str` (texto) → `bytes` = **encode** (serialização)
  - `bytes` → `str` (texto) = **decode** (desserialização)

> 📖 **Conceito:** `sendall()` só aceita `bytes`. Por isso todo texto passa por
> `.encode("utf-8")` antes de sair, e por `.decode("utf-8")` antes de ser exibido.

## 1.4 — `parsear()` (linhas 75 a 97) — DESSERIALIZAÇÃO + validação

```python
def parsear(linha: str) -> tuple:
```
Recebe uma `str` (uma linha já "crua" da rede) e retorna uma **tupla**
`(tipo, dados)`.

```python
    linha = linha.rstrip("\r\n")
```
Remove `\n` (e `\r`, caso venha de sistemas Windows) do **final**. `rstrip` só
remove do lado direito.

```python
    if not linha:
        raise ValueError("Mensagem vazia")
```
Se, após limpar, não sobrou nada → erro.

```python
    if SEPARADOR not in linha:
        raise ValueError(f"Mensagem sem separador {SEPARADOR!r}: {linha!r}")
```
Se não tem `:` → a mensagem não segue o formato → erro.

```python
    tipo, dados = linha.split(SEPARADOR, 1)
```
**Ponto-chave:** o `1` no `split(":", 1)` significa "quebre **apenas uma vez**".
Assim, se os dados contiverem `:`, eles são preservados:

```text
Entrada : "HELLO:http://site.com:8080"
split com maxsplit=1  →  tipo="HELLO",  dados="http://site.com:8080"   ✅
split sem maxsplit    →  ["HELLO", "http://site", "com", "8080"]       ❌ (quebraria)
```

```python
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo de mensagem desconhecido: {tipo!r}")
```
Valida se o tipo recebido é conhecido pelo protocolo (ex.: `"FOO"` → erro).

```python
    if len(dados) > MAX_DADOS:
        raise ValueError(...)
    return tipo, dados
```
Valida o tamanho e devolve a tupla `(tipo, dados)`.

> 📖 **Segurança/robustez:** o `parsear` **nunca confia** no que veio da rede.
> Tudo é validado. Isso se chama "validação de entrada" (*input validation*).

## 1.5 — `receber_mensagem()` (linhas 100 a 123) — FRAMING + BUFFER

> ⭐ **Esta é a função MAIS importante do projeto para explicar na apresentação.**

```python
def receber_mensagem(sock, buffer: bytearray):
```
- `sock`: o socket conectado (de `server` ou `client`).
- `buffer`: **lista de bytes acumuladora**, mantida **entre** as chamadas.

```python
    while DELIMITADOR.encode() not in buffer:
        pedaco = sock.recv(4096)
        if not pedaco:
            # Outra ponta encerrou a conexão de forma limpa (FIN)
            return None
        buffer.extend(pedaco)
```

**Passo a passo:**
1. `while "\n" não está no buffer`: continua lendo até achar o fim de uma mensagem.
2. `sock.recv(4096)`: lê até 4096 bytes do fluxo TCP. **Pode vir menos** (1 byte,
   3 bytes, 2 mensagens de uma vez...).
3. `if not pedaco:` → `recv` retornou `b""` (vazio). **Isso significa que a outra
   ponta enviou `FIN`** (fechou a conexão) → retorna `None` ("conexão encerrada").
4. `buffer.extend(pedaco)`: **acrescenta** os bytes novos ao final do buffer.

```python
    indice = buffer.index(DELIMITADOR.encode())
    linha_bytes = bytes(buffer[: indice + 1])
    del buffer[: indice + 1]

    return parsear(linha_bytes.decode("utf-8"))
```

**Quando acha o `\n`:**
1. `buffer.index(b"\n")`: encontra a POSIÇÃO do delimitador.
2. `buffer[:indice+1]`: extrai da posição 0 até o `\n` (**uma mensagem inteira**).
3. `del buffer[:indice+1]`: **apaga** essa parte do buffer, deixando o resto
   (eventualmente a PRÓXIMA mensagem já recebida) para a próxima chamada.
4. `.decode("utf-8")`: bytes → texto.
5. `parsear(...)`: valida e retorna `(tipo, dados)`.

### 🧠 Por que isso é necessário? (o conceito que mais cai em prova)

O TCP é um **fluxo de bytes** (*byte stream*). O SO não preserva fronteiras de
`send()`. Exemplo — cliente faz 2 `sendall()`:

```text
Envio 1: b"HELLO:oi\n"        (9 bytes)
Envio 2: b"PING\n"            (5 bytes)
```

O servidor poderia receber de formas DIFERENTES em cada `recv()`:

| Cenário | `recv(4096)` retornaria | Problema |
| :--- | :--- | :--- |
| A (ideal) | `b"HELLO:oi\n"` e depois `b"PING\n"` | OK |
| B (tudo junto) | `b"HELLO:oi\nPING\n"` | 2 mensagens em 1 recv |
| C (fragmentado) | `b"HELLO:o"` e depois `b"i\nPING\n"` | Mensagem quebrada no meio |

O **buffer acumulador + `\n`** resolve TODOS os cenários: ele só entrega ao
`parsear` uma linha **completa**. É o chamado **framing baseado em delimitador**.

> 📖 Outras técnicas de framing (vale citar na apresentação):
> - **Delimitador** (o nosso, `\n`) — usado por HTTP, SMTP.
> - **Tamanho fixo** (ex.: cabeçalho de N bytes).
> - **Contagem** (ex.: primeiro campo diz quantos bytes vêm depois) — usado por Redis, MQTT.

---

# PARTE 2 — `server.py` (o processo passivo)

> Fluxo do servidor: `socket → bind → listen → accept → (loop recv/send) → close`

## 2.1 — Imports (linhas 19 a 33)

```python
import socket
import sys

from protocol import (
    DELIMITADOR, TIPO_ACK, TIPO_ECHO, TIPO_ERROR, TIPO_EXIT,
    TIPO_HELLO, TIPO_PING, TIPO_PONG, criar_mensagem, receber_mensagem,
)
```
- `socket`: biblioteca padrão de rede do Python (primitivas de sockets).
- `sys`: acesso a argumentos de linha de comando (`sys.argv`) e `sys.exit()`.
- `from protocol import ...`: importa o "idioma" compartilhado.

## 2.2 — Configuração (linhas 35 a 40)

```python
HOST = "0.0.0.0"  # escuta em todas as interfaces de rede
try:
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
except ValueError:
    print(f"[Erro] Porta inválida: {sys.argv[1]!r}. Use um número (ex.: 5000).")
    sys.exit(1)
```

| Trecho | Significado |
| :--- | :--- |
| `"0.0.0.0"` | Endereço **mágico** = "escuta em TODAS as interfaces de rede" (eth0, wlan0, loopback). Se fosse `"127.0.0.1"`, só aceitaria conexões locais. |
| `sys.argv[1]` | Primeiro argumento passado no terminal (`python3 server.py 6000` → `argv[1]="6000"`). |
| `int(...)` | Converte texto → número (a porta é um número). |
| `else 5000` | Se não passou argumento, usa a porta padrão 5000. |
| `except ValueError` | Se passou algo não numérico (ex.: `abc`), avisa e sai. |
| `sys.exit(1)` | Encerra o processo com código de erro (1 = falha; 0 = sucesso). |

> 📖 **Porta lógica**: identifica o processo dentro de uma máquina (0–65535).
> Portas `< 1024` são "privilegiadas" (precisam de root). `5000` é comum em apps.

## 2.3 — Criação do socket e opções (linhas 42 a 44)

```python
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
```

| Primitiva | Argumentos | O que faz | Conceito |
| :--- | :--- | :--- | :--- |
| `socket.socket()` | `AF_INET` | Usa **IPv4** (endereços 32-bit, ex.: 192.168.1.15) | Camada de Rede |
| | `SOCK_STREAM` | Usa **TCP** (fluxo de bytes confiável, orientado à conexão) | Camada de Transporte |
| `setsockopt()` | `SO_REUSEADDR, 1` | Permite **reusar a porta imediatamente** após o servidor morrer | Evita erro "Address already in use" (TIME_WAIT) |

> ⚠️ **`SOCK_STREAM` = TCP**  |  `SOCK_DGRAM` = UDP.
> Essa é a linha que **escolhe o protocolo de transporte**. Se mudasse para
> `SOCK_DGRAM`, o resto do código (connect/accept) teria que mudar todo.

> 📖 **TIME_WAIT:** depois de fechar uma conexão, o SO "segura" a porta por ~60s
> para evitar colisão de pacotes atrasados. `SO_REUSEADDR` contorna isso ao
> reiniciar o servidor para testes.

## 2.4 — `bind` e `listen` (linhas 46 a 54)

```python
try:
    try:
        server.bind((HOST, PORT))
    except OSError as erro:
        print(f"[Erro] Não foi possível abrir a porta {PORT}: {erro}")
        print("Verifique se ela já está em uso ou se há permissão (portas < 1024).")
        sys.exit(1)

    server.listen(1)
```

| Primitiva | O que faz | Conceito |
| :--- | :--- | :--- |
| `bind((HOST, PORT))` | **Associa** o socket a uma interface + porta locais | Prepara o "telefone" para tocar naquele número |
| `except OSError` | Pega erro de "porta em uso" ou "permissão negada" | Tratamento de erro do bind |
| `listen(1)` | Coloca em **modo passivo** (escuta). `1` = tamanho da **fila** de conexões pendentes | Backlog |

> 📖 **Diferença crucial (cai MUITO):**
> - `bind()` = "vou atender neste número" (endereça).
> - `listen()` = "vou **poder** atender chamadas" (modo servidor / passivo).
> - `accept()` = "atendo **UMA** chamada específica e falo com aquela pessoa".
>
> `backlog=1` significa: se chegarem 3 clientes ao mesmo tempo, 1 fala com você
> e os outros esperam (ou são recusados). É por isso o nosso servidor é
> **single-client**.

## 2.5 — `accept` (linhas 63 a 67)

```python
conn, address = server.accept()
print(f"\n[+] Cliente conectado: {address[0]}:{address[1]}")
print(f"[i] Protocolo: <TIPO>:<DADOS>{DELIMITADOR!r}\n")

buffer = bytearray()
```

- `accept()` **bloqueia** a execução até um cliente conectar (faz o *handshake*).
- Retorna **dois sockets conceitualmente distintos**:
  - `conn`: um **NOVO socket dedicado** a ESTA conexão (por aqui você fala com o cliente).
  - `address`: tupla `(ip, porta_remota)` do cliente.
- `address[0]` = IP do cliente; `address[1]` = porta efêmera dele.
- `buffer = bytearray()`: cria o buffer acumulador **dessa conexão** (vazio).

> 📖 **Por que um socket novo (`conn`) e não usar o `server`?**
> Porque o socket `server` serve **só para aceitar**. Cada cliente conectado ganha
> seu próprio `conn` (e poderia ter seu próprio thread). O `server` continua
> livre para aceitar outros (mas nosso código para em 1, por decisão didática).

## 2.6 — Loop principal de recepção (linhas 69 a 89)

```python
try:
    while True:
        try:
            resultado = receber_mensagem(conn, buffer)
        except ValueError as erro:
            print(f"[!] Mensagem inválida recebida: {erro}")
            conn.sendall(criar_mensagem(TIPO_ERROR, f"formato_invalido: {erro}"))
            continue
        except UnicodeDecodeError:
            print("[!] Recebido dado com encoding inválido.")
            conn.sendall(criar_mensagem(TIPO_ERROR, "encoding_invalido"))
            continue
```

- `while True`: loop infinito de conversa (sai só via `break` ou exceção).
- `receber_mensagem(...)`: lê **uma mensagem completa** (usa o framing).
- **Se o parse falhar** (`ValueError`): o servidor **não morre**. Ele:
  1. avisa no console,
  2. responde `ERROR:formato_invalido...` ao cliente,
  3. `continue` → volta ao início do loop e segue no ar.
- **Se o bytes forem inválidos em UTF-8** (`UnicodeDecodeError`): mesma lógica,
  responde `ERROR:encoding_invalido`.

> 💡 **Robustez:** um servidor que **não derruba** por 1 mensagem ruim é um
> servidor **robusto**. Isso pontua em "Tratamento de erros".

```python
        if resultado is None:
            print("\n[-] O cliente encerrou a conexão.")
            break
```
- `None` = `recv` retornou `b""` = cliente enviou **`FIN`** (fechou limpo).
- Sai do loop com `break`.

```python
        tipo, dados = resultado
        print(f" Cliente [{tipo}]: {dados}")
```
- Desempacota a tupla `(tipo, dados)`.
- Mostra o que chegou no console do servidor.

## 2.7 — Máquina de estados: o que responder a cada tipo (linhas 91 a 109)

```python
        if tipo == TIPO_HELLO:
            try:
                resposta = input(" Servidor: ")
            except EOFError:
                conn.sendall(criar_mensagem(TIPO_ACK, "servidor_encerrando"))
                break
            conn.sendall(criar_mensagem(TIPO_ACK, resposta))
```
- **HELLO** (mensagem de chat): o servidor pede uma resposta ao operador via
  `input()`, e devolve `ACK:<resposta>`.
- `except EOFError`: se a entrada padrão fechar (Ctrl+D ou pipe), avisa e sai.
- `sendall()`: envia **todos** os bytes (diferente de `send()`, que pode enviar
  menos que o total e exigiria tratar o resto).

```python
        elif tipo == TIPO_ECHO:
            conn.sendall(criar_mensagem(TIPO_ECHO, dados))
```
- **ECHO**: devolve os MESMOS dados. Serve para testar ida e volta (e aparece
  bonito no Wireshark).

```python
        elif tipo == TIPO_PING:
            conn.sendall(criar_mensagem(TIPO_PONG, ""))
```
- **PING** → responde **PONG**. É um *keep-alive* / "você está vivo?".

```python
        elif tipo == TIPO_EXIT:
            conn.sendall(criar_mensagem(TIPO_ACK, "sessao_encerrada"))
            print("[*] Cliente solicitou o encerramento da sessão.")
            break
```
- **EXIT**: confirma com `ACK` e encerra o loop (sessão terminada de forma limpa).

> 📖 **Nota didática:** repare que o `if/elif` implementa o **"comportamento do
> servidor"** — é uma **máquina de estados** simples: para cada tipo recebido,
> uma ação. Se chegasse um tipo novo, cairia sem resposta (por isso validamos
> os tipos no protocolo).

## 2.8 — Tratamento de exceções de rede e encerramento (linhas 111 a 123)

```python
except ConnectionResetError:
    print("\n[-] Conexão resetada pelo cliente (RST).")
except (BrokenPipeError, ConnectionError) as erro:
    print(f"\n[-] Conexão perdida com o cliente: {erro}")
finally:
    conn.close()
    print("[*] Conexão com o cliente fechada.")
```

| Exceção | Quando ocorre | Conceito TCP |
| :--- | :--- | :--- |
| `ConnectionResetError` | Cliente morreu/abortou → mandou **RST** (abortivo) | Fechamento **brusco** (RST) |
| `BrokenPipeError` | Você tentou **enviar** para alguém que já fechou | Tentativa de escrita após FIN alheio |
| `ConnectionError` | Classe genérica que cobre os dois acima | — |
| `finally:` | Executa **sempre** (erro ou não) → garante `close()` | Libera o socket |

```python
except KeyboardInterrupt:
    print("\n\n[!] Servidor finalizado pelo usuário.")
finally:
    server.close()
    print("[*] Socket do servidor finalizado com sucesso.")
```
- `KeyboardInterrupt` = **Ctrl+C** → encerramento gracioso.
- `finally` do `try` externo: fecha o socket `server` (o de escuta).
- `close()` envia o **FIN** e libera o recurso de rede.

> 📖 **`finally` é fundamental:** garante que o socket NUNQUE fique "vazando"
> (file descriptor aberto), mesmo se der erro ou Ctrl+C.

---

# PARTE 3 — `client.py` (o processo ativo)

> Fluxo do cliente: `socket → connect → (loop send/recv) → close`

## 3.1 — Imports (linhas 17 a 30)

Mesma estrutura do servidor, mas importa os tipos que o **cliente usa/lê**.

## 3.2 — Configuração (linhas 32 a 38)

```python
HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
try:
    PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
except ValueError:
    print(f"[Erro] Porta inválida: {sys.argv[2]!r}. Use um número (ex.: 5000).")
    sys.exit(1)
```
- `sys.argv[1]` = **IP do servidor** (padrão `127.0.0.1`).
- `sys.argv[2]` = **porta** do servidor (padrão 5000).
- Uso: `python3 client.py 192.168.1.15 5000`.

> 📖 `127.0.0.1` = **loopback** (localhost). Toda máquina tem esse IP; serve para
> testar cliente e servidor na MESMA máquina sem sair para a rede física.

## 3.3 — Criação do socket + timeout (linhas 40 a 41)

```python
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.settimeout(10)
```
- `SOCK_STREAM` → **TCP** (mesmo do servidor).
- `settimeout(10)`: se a conexão/leitura demorar mais que 10s, **não trava
  para sempre** → levanta `TimeoutError`.

> 💡 Sem timeout, um `connect()` para um IP que não responde poderia travar o
> programa por minutos. Timeout = **robustez**.

## 3.4 — Conexão (linhas 43 a 50)

```python
try:
    print(f"[*] Conectando ao servidor em {HOST}:{PORT}...")
    client.connect((HOST, PORT))
    client.settimeout(None)
    print("[+] Conectado ao servidor!")
    print("Comandos: '/eco <texto>', '/ping', '/sair' (ou digite uma mensagem).")

    buffer = bytearray()
```

| Linha | Significado | Conceito |
| :--- | :--- | :--- |
| `connect((HOST, PORT))` | Inicia a conexão → dispara o **Three-Way Handshake** (SYN → SYN/ACK → ACK) | Só retorna DEPOIS do handshake completar (ou dar erro) |
| `settimeout(None)` | Volta a ser **bloqueante** (espera o tempo que for preciso) | Conectou; agora quer esperar as respostas normalmente |
| `buffer = bytearray()` | Buffer de leitura **desta conexão** | Mesmo mecanismo de framing do servidor |

> 📖 `connect()` é o **cliente** que dispara. O `accept()` do servidor é quem
> "escuta" esse pacote SYN. **Só o cliente conecta; só o servidor aceita.**

## 3.5 — Loop: ler comando do usuário (linhas 52 a 61)

```python
    while True:
        try:
            texto = input("Você: ")
        except EOFError:
            break

        texto = texto.strip()
        if not texto:
            continue
```
- `input()`: lê a linha digitada pelo usuário.
- `EOFError`: Ctrl+D (ou fim de pipe) → sai do loop.
- `.strip()`: remove espaços das pontas.
- `if not texto: continue`: ignora linhas vazias (não envia nada).

## 3.6 — Máquina de comandos: texto → mensagem do protocolo (linhas 63 a 75)

```python
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
```

| Digitado pelo usuário | Mensagem enviada | Observação |
| :--- | :--- | :--- |
| `/sair` | `EXIT:bye\n` | Encerra a sessão |
| `/ping` | `PING\n` | Não espera resposta aqui (usa `continue`) |
| `/eco oi` | `ECHO:oi\n` | `texto[5:]` remove o `/eco ` (5 caracteres) |
| qualquer outra frase | `HELLO:<frase>\n` | Mensagem de chat normal |

> 💡 `.lower()` torna o comando **case-insensitive** (`/SAIR` funciona igual).
> `startswith("/eco ")` detecta o comando com argumento.

## 3.7 — Aguardar e interpretar a resposta (linhas 77 a 101)

```python
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
```
Mesma lógica de robustez do servidor: parse inválido ou encoding ruim → avisa e
seguue; `None` → servidor mandou `FIN` → sai.

```python
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
```
- Desempacota `(tipo, dados)` e **formata a saída** conforme o tipo recebido.
- `ERROR` → mostra o motivo em destaque.
- `ACK` → é a resposta de chat ("Servidor: ...").
- `ECHO` → eco devolvido.
- `else`: fallback (não deve ocorrer, pois o protocolo já validou os tipos).

## 3.8 — Tratamento de erros de conexão (linhas 103 a 120)

```python
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
```

**Tabela de erros do cliente (MEMORIZE — cobra em "tratamento de erros"):**

| Exceção | Situação real | O que a rede fez |
| :--- | :--- | :--- |
| `ConnectionRefusedError` | Servidor **desligado** (porta aberta, mas ninguém escuta) | Respondeu **RST** → cliente sabe que recusou |
| `socket.gaierror` | IP/host **inexistente** (falha de resolução/DNS) | Nem chegou a conectar |
| `TimeoutError` | Servidor **não respondeu** em 10s (rede bloqueada, host fora) | Silêncio na rede |
| `ConnectionResetError` | Servidor **abortou** no meio | Mandou **RST** |
| `BrokenPipeError` | Tentou enviar após o outro já fechou | FIN do outro lado |
| `KeyboardInterrupt` | **Ctrl+C** | Interrupção local |

- `finally` → `client.close()`: fecha o socket (envia FIN) **sempre**.

> 📖 **SYN vs RST — conceito de prova:**
> - Tentar conectar a porta **fechada** → servidor responde **RST** →
>   `ConnectionRefusedError`.
> - Tentar conectar a IP que **não responde** (firewall descarta) → **silêncio** →
>   `TimeoutError`.
> Essa distinção mostra que você entende a diferença entre "recusa" e "mudeza".

---

# PARTE 4 — Fluxos completos (memorize as sequências)

## 4.1 — Fluxo normal de uma mensagem de chat

```text
USUÁRIO        CLIENTE                REDE/TCP              SERVIDOR        USUÁRIO
   │ digita "oi"  │                      │                     │              │
   │──────────────►│                      │                     │              │
   │               │ criar_mensagem(HELLO,"oi") → b"HELLO:oi\n"│              │
   │               │ sendall() ──────────►│                     │              │
   │               │        [TCP segmenta, encaminha, ACK]     │              │
   │               │                      │── recv() ──────────►│              │
   │               │                      │   receber_mensagem  │ mostra       │
   │               │                      │   (buffer+\\n)      │─────────────►│
   │               │                      │                     │ input()      │
   │               │                      │                     │◄─────────────│ digita "tudo"
   │               │◄── recv() ───────────│◄─ sendall(ACK:tudo) │              │
   │  mostra       │ receber_mensagem     │                     │              │
   │◄──────────────│ (tipo=ACK)           │                     │              │
```

## 4.2 — Fluxo de conexão (handshake) e desligamento

```text
   INÍCIO (3 vias)                                 FIM (FIN, 4 passos)
   ─────────────────                               ────────────────────
   cliente ──SYN────►  (1)                        cliente ──FIN──► (1)
   cliente ◄─SYN,ACK─  (2)                        cliente ◄─ACK─  (2)
   cliente ──ACK────►  (3)                        cliente ◄─FIN─  (3)
   ✅ conectado                                     cliente ──ACK─► (4)
                                                   ✅ fechado
```
- No Wireshark você verá exatamente esses pacotes na porta 5000.

## 4.3 — Fluxo de erro: mensagem malformada (robustez)

```text
CLIENTE (ou atacante)            SERVIDOR
   │  envia "ERRADO sem prot\n"     │
   │───────────────────────────────►│ receber_mensagem → parsear → ValueError
   │                                │ [!] log no console
   │◄────── ERROR:formato_invalido  │ sendall (não MORRE, só avisa)
   │                                │ continua no while True ✅
   │  envia "PING\n"                │
   │───────────────────────────────►│ (servidor vivo!)
   │◄───────────── PONG             │
```

---

# PARTE 5 — Resumo de conceitos de Redes (para a apresentação)

## 5.1 — As 10 perguntas do enunciado (respostas-memorização)

| # | Pergunta | Resposta curta (falar na apresentação) |
| :--- | :--- | :--- |
| 1 | **Qual problema resolve?** | Comunicação bidirecional confiável de texto entre 2 processos em máquinas distintas. |
| 2 | **Quem são os processos?** | `client.py` (ativo) e `server.py` (passivo) + `protocol.py` (formato compartilhado). |
| 3 | **Como ocorre a comunicação?** | Servidor `bind/listen/accept`; cliente `connect` (handshake); trocam mensagens `sendall/recv` com protocolo `<TIPO>:<DADOS>\n`; fecham com `close` (FIN). |
| 4 | **Qual transporte?** | **TCP** (`SOCK_STREAM`). |
| 5 | **Por que TCP é adequado?** | Chat exige entrega confiável, ordenada, sem perdas; TCP faz ACK, retransmissão, reordenação e detecta desconexão (FIN/RST). |
| 6 | **Qual o protocolo da aplicação?** | Texto `<TIPO>:<DADOS>\n` com 7 tipos e framing por `\n` (definido em `protocol.py`). |
| 7 | **Quais mensagens?** | `HELLO`, `ECHO`, `PING`, `PONG`, `ACK`, `EXIT`, `ERROR`. |
| 8 | **E se fosse UDP?** | Sem conexão, sem confiabilidade: poderia perder, duplicar ou reordenar mensagens; sem FIN (não detectaria saída); teríamos que implementar confiabilidade/keep-alive (`PING`/`PONG`) nós mesmos. |
| 9 | **Quais erros podem ocorrer?** | Conexão recusada, IP inválido, timeout, reset (RST), broken pipe, mensagem malformada, encoding inválido, porta em uso. |
| 10 | **Como são tratados?** | `try/except` específicos por exceção + `finally` fechando sockets; servidor responde `ERROR` e **não derruba** o loop; validação de entrada no protocolo. |

## 5.2 — Tabela-primitivas (decorar)

| Primitiva | Camada/Conceito | Onde no código |
| :--- | :--- | :--- |
| `socket(AF_INET, SOCK_STREAM)` | Transporte (TCP) + Rede (IPv4) | `server.py:42`, `client.py:40` |
| `setsockopt(SO_REUSEADDR)` | Config. de socket (reuso de porta) | `server.py:44` |
| `bind((HOST,PORT))` | Rede/Transporte (endereça) | `server.py:48` |
| `listen(backlog)` | Modo passivo (escuta) | `server.py:54` |
| `accept()` | Aceita 1 conexão (novo socket) | `server.py:63` |
| `connect((HOST,PORT))` | Handshake (só cliente) | `client.py:45` |
| `sendall(bytes)` | Envia todos os bytes | ambos |
| `recv(4096)` | Lê até 4096 bytes (pode vir menos!) | `protocol.py:111` |
| `settimeout(n)` | Evita bloqueio infinito | `client.py:41` |
| `close()` | Envia FIN e libera | `finally` de ambos |

## 5.3 — Erros de transporte: qual exceção, qual pacote

| Situação | Pacote TCP | Exceção Python |
| :--- | :--- | :--- |
| Porta fechada no destino | **RST** | `ConnectionRefusedError` |
| Host fora / firewall descarta | (silêncio) | `TimeoutError` |
| Processo morre no meio | **RST** | `ConnectionResetError` |
| Fechamento limpo | **FIN** | `recv` → `b""` → `None` |
| Escrever após o outro fechar | — | `BrokenPipeError` |

## 5.4 — TCP vs UDP (compare e memorize)

| Aspecto | TCP (nosso) | UDP |
| :--- | :--- | :--- |
| Conexão | Sim (handshake) | Não |
| Confiável | Sim (ACK/retransmite) | Não |
| Ordenado | Sim | Não |
| Detecção de desconexão | Sim (FIN/RST) | Não (precisa app) |
| Primitivas | `connect/accept` | `sendto/recvfrom` |
| Overhead | Maior | Menor |
| Bem para | Chat, HTTP, FTP | Streaming, DNS, jogos, VoIP |
| Python (`socket`) | `SOCK_STREAM` | `SOCK_DGRAM` |

## 5.5 — Onde aplicar o Wireshark (guia de análise)

1. Captura na interface correta (ou **Loopback** para teste local).
2. Filtro: **`tcp.port == 5000`**.
3. Procure e **identifique**:
   - **Handshake**: `SYN`, `SYN,ACK`, `ACK` (início).
   - **Dados**: payloads `HELLO:...`, `ACK:...`, `PING`, `PONG` (campo *Info*/*Data*).
   - **ACKs de transporte**: números de sequência/acknowledgment (confirmação do TCP).
   - **Fecho**: sequência de `FIN`/`ACK` (duas fases).
4. **`Analyze → Follow → TCP Stream`** → mostra a conversa em texto puro,
   evidenciando o protocolo `<TIPO>:<DADOS>` trafegando.

---

# PARTE 6 — Flashcards de fixação (auto-teste)

Responda em voz alta antes de olhar a resposta.

**P1.** Por que `recv()` pode retornar menos que o total enviado, e como resolvemos isso?
<details><summary>Resposta</summary> Porque TCP é um fluxo de bytes sem fronteiras de mensagem. Resolvemos com **framing** por `\n` + **buffer acumulador** (`receber_mensagem`).</details>

**P2.** O que `SOCK_STREAM` e `SOCK_DGRAM` significam?
<details><summary>Resposta</summary> `SOCK_STREAM` = TCP; `SOCK_DGRAM` = UDP.</details>

**P3.** Qual a diferença entre `bind()`, `listen()` e `accept()`?
<details><summary>Resposta</summary> `bind` = endereça (interface+porta); `listen` = entra em modo passivo (fila); `accept` = atende 1 cliente e devolve socket dedicado `conn`.</details>

**P4.** O que significa `recv()` retornar `b""`?
<details><summary>Resposta</summary> A outra ponta enviou **FIN** (fechamento limpo). Nossa função retorna `None`.</details>

**P5.** Qual a diferença prática entre `send()` e `sendall()`?
<details><summary>Resposta</summary> `send()` pode enviar MENOS bytes (precisa tratar o resto); `sendall()` envia TODOS e só retorna quando tudo for enviado.</details>

**P6.** Cliente manda `"ERRO sem dois pontos"` — o que o servidor faz?
<details><summary>Resposta</summary> `parsear` levanta `ValueError`; o servidor manda `ERROR:formato_invalido` e **continua no loop** (não derruba).</details>

**P7.** O que `127.0.0.1` e `0.0.0.0` significam?
<details><summary>Resposta</summary> `127.0.0.1` = loopback (só a própria máquina). `0.0.0.0` = escuta em TODAS as interfaces.</details>

**P8.** Por que o `SO_REUSEADDR`?
<details><summary>Resposta</summary> Evita o erro "Address already in use" ao reiniciar rápido (contorna o estado TIME_WAIT).</details>

**P9.** Por que `finally: socket.close()` em ambos?
<details><summary>Resposta</summary> Garante que o socket seja fechado em QUALQUER cenário (erro, Ctrl+C, fim normal), enviando FIN e liberando recursos.</details>

**P10.** Se fosse UDP, o que mudaria neste código?
<details><summary>Resposta</summary> Trocaria `SOCK_STREAM`→`SOCK_DGRAM`; usaria `sendto/recvfrom` (sem `connect/accept`); perderíamos confiabilidade, ordenação e detecção de desconexão — teríamos que implementar na aplicação.</details>

---

## ✅ Checklist final para a apresentação

- [ ] Explicar o **problema** e os **2 processos** (cliente/servidor)
- [ ] Mostrar a **arquitetura** e o fluxo de sockets
- [ ] Justificar o **TCP** (confiável, ordenado, detecta desconexão)
- [ ] Explicar o **protocolo próprio** `<TIPO>:<DADOS>\n` e os 7 tipos
- [ ] Destacar o **framing + buffer** (o porquê do TCP exigir isso)
- [ ] Rodar a **demonstração** (chat, `/ping`, `/eco`, `/sair`)
- [ ] Mostrar o **Wireshark**: handshake, dados, fecho (`Follow TCP Stream`)
- [ ] Listar os **erros tratados** e como (tabela 5.3)
- [ ] Responder às 10 perguntas do enunciado (tabela 5.1)

> 💡 **Dica de ouro para decorar o fluxo:** abra os 3 arquivos e siga UMA mensagem
> de chat do início ao fim: `input()` → `criar_mensagem` → `sendall` → (rede) →
> `receber_mensagem` (buffer+`\n`) → `parsear` → `if HELLO` → `input()` →
> `criar_mensagem(ACK)` → `sendall` → (rede) → cliente `receber_mensagem` →
> `parsear` → imprimir. Esse ciclo é o coração de todo o projeto.
