"""
Protocolo de Aplicação — Chat TCP Cliente-Servidor
==================================================

Formato de cada mensagem (uma por linha):

    <TIPO>:<DADOS>\n

- <TIPO>:  identificador da mensagem (ex.: HELLO, ACK, ERROR).
- <DADOS>: conteúdo textual (pode conter o caractere ':', espaços, acentos).
- '\n':    delimitador de fim de mensagem (framing sobre o fluxo TCP).

Tipos válidos:
    C -> S (cliente para servidor)
        HELLO : mensagem de chat do usuário
        ECHO  : solicita eco (o servidor devolve os mesmos dados)
        PING  : keep-alive / teste de conectividade
        EXIT  : cliente deseja encerrar a sessão

    S -> C (servidor para cliente)
        ACK   : confirmação de recebimento
        PONG  : resposta ao PING
        ECHO  : resposta ao ECHO (eco dos dados)
        ERROR : erro de protocolo (dados indicam o motivo)
"""

# ---------------------------------------------------------------------------
# Constantes do protocolo
# ---------------------------------------------------------------------------

SEPARADOR = ":"      # separa <TIPO> dos <DADOS>
DELIMITADOR = "\n"   # delimita o fim de uma mensagem no fluxo de bytes

MAX_DADOS = 4096     # limite dos dados (payload) de uma mensagem

# Tipos de mensagem
TIPO_HELLO = "HELLO"  # C -> S : mensagem de chat
TIPO_ECHO = "ECHO"    # C -> S : solicita eco ; S -> C : eco retornado
TIPO_PING = "PING"    # C -> S : keep-alive
TIPO_PONG = "PONG"    # S -> C : resposta ao PING
TIPO_ACK = "ACK"      # S -> C : confirmação
TIPO_EXIT = "EXIT"    # C -> S : encerrar sessão
TIPO_ERROR = "ERROR"  # S -> C : erro de protocolo

TIPOS_CLIENTE_SERVIDOR = {TIPO_HELLO, TIPO_ECHO, TIPO_PING, TIPO_EXIT}
TIPOS_SERVIDOR_CLIENTE = {TIPO_ACK, TIPO_PONG, TIPO_ECHO, TIPO_ERROR}
TIPOS_VALIDOS = TIPOS_CLIENTE_SERVIDOR | TIPOS_SERVIDOR_CLIENTE


# ---------------------------------------------------------------------------
# Funções do protocolo
# ---------------------------------------------------------------------------

def criar_mensagem(tipo: str, dados: str = "") -> bytes:
    """Monta uma mensagem do protocolo e retorna os bytes a serem enviados.

    Formato: b"<TIPO>:<DADOS>\\n"

    Levanta ValueError se o tipo for inválido ou os dados excederem MAX_DADOS.
    """
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo de mensagem inválido: {tipo!r}")

    if len(dados) > MAX_DADOS:
        raise ValueError(
            f"Dados excedem o limite de {MAX_DADOS} caracteres "
            f"(recebidos: {len(dados)})"
        )

    # .replace evita que um '\\n' nos dados quebre o framing
    linha = f"{tipo}{SEPARADOR}{dados.replace(chr(10), ' ')}{DELIMITADOR}"
    return linha.encode("utf-8")


def parsear(linha: str) -> tuple:
    """Parseia uma linha do protocolo e retorna (tipo, dados).

    Levanta ValueError se a linha estiver malformada.
    """
    linha = linha.rstrip("\r\n")

    if not linha:
        raise ValueError("Mensagem vazia")

    if SEPARADOR not in linha:
        raise ValueError(f"Mensagem sem separador {SEPARADOR!r}: {linha!r}")

    # Separa apenas no primeiro ':', permitindo que os dados contenham ':'
    tipo, dados = linha.split(SEPARADOR, 1)

    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo de mensagem desconhecido: {tipo!r}")

    if len(dados) > MAX_DADOS:
        raise ValueError(f"Dados excedem o limite de {MAX_DADOS} caracteres")

    return tipo, dados


def receber_mensagem(sock, buffer: bytearray):
    """Recebe uma mensagem completa do socket, usando um buffer acumulador.

    O TCP é um fluxo de bytes: uma chamada recv() NÃO garante que chegará
    uma mensagem inteira. Esta função acumula bytes no `buffer` até encontrar
    o delimitador '\\n', devolvendo uma mensagem completa por vez.

    Retorna (tipo, dados) ou None se a conexão for encerrada pela outra ponta.
    Levanta ValueError se a mensagem recebida for malformada.
    """
    while DELIMITADOR.encode() not in buffer:
        pedaco = sock.recv(4096)
        if not pedaco:
            # Outra ponta encerrou a conexão de forma limpa (FIN)
            return None
        buffer.extend(pedaco)

    # Extrai uma linha completa (até e incluindo o '\n') e deixa o restante
    # no buffer para a próxima chamada
    indice = buffer.index(DELIMITADOR.encode())
    linha_bytes = bytes(buffer[: indice + 1])
    del buffer[: indice + 1]

    return parsear(linha_bytes.decode("utf-8"))
