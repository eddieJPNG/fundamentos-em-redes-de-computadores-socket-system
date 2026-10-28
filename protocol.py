"""
Protocolo de Aplicação — Chat TCP Cliente-Servidor
==================================================

Formato de cada mensagem (uma por linha):

    <TIPO>:<DADOS>\n

- <TIPO>:  identificador da mensagem (ex.: HELLO, MSG, ERROR).
- <DADOS>: conteúdo textual (pode conter o caractere ':', espaços, acentos).
- '\n':    delimitador de fim de mensagem (framing sobre o fluxo TCP).

Tipos válidos:
    C -> S (cliente para servidor)
        HELLO : mensagem de chat do usuário
        ECHO  : solicita eco (o servidor devolve os mesmos dados)
        PING  : keep-alive / teste de conectividade
        EXIT  : cliente deseja encerrar a sessão

    S -> C (servidor para cliente)
        MSG   : resposta do operador a uma mensagem de chat
        PONG  : resposta ao PING
        ECHO  : resposta ao ECHO (eco dos dados)
        BYE   : confirmação de encerramento / aviso de desligamento
        ERROR : erro de protocolo (dados indicam o motivo)

Observação sobre sincronismo (request/response):
    O protocolo é "lockstep": todo ENVIO deve ser seguido de exatamente
    UMA leitura da resposta correspondente. Enviar sem ler (ou ler sem
    enviar) desloca a conversa em uma mensagem e nunca mais se recupera.
"""

# ---------------------------------------------------------------------------
# Constantes do protocolo
# ---------------------------------------------------------------------------

SEPARADOR = ":"      # separa <TIPO> dos <DADOS>
DELIMITADOR = "\n"   # delimita o fim de uma mensagem no fluxo de bytes

MAX_DADOS = 4096     # limite dos dados (payload) de uma mensagem
MAX_BUFFER = 8192    # limite do buffer acumulador (evita crescimento sem teto)

# Tipos de mensagem
TIPO_HELLO = "HELLO"  # C -> S : mensagem de chat
TIPO_ECHO = "ECHO"    # C -> S : solicita eco ; S -> C : eco retornado
TIPO_PING = "PING"    # C -> S : keep-alive
TIPO_PONG = "PONG"    # S -> C : resposta ao PING
TIPO_MSG = "MSG"      # S -> C : resposta do operador ao chat
TIPO_BYE = "BYE"      # S -> C : sessão encerrada / servidor saindo
TIPO_EXIT = "EXIT"    # C -> S : encerrar sessão
TIPO_ERROR = "ERROR"  # S -> C : erro de protocolo

TIPOS_CLIENTE_SERVIDOR = {TIPO_HELLO, TIPO_ECHO, TIPO_PING, TIPO_EXIT}
TIPOS_SERVIDOR_CLIENTE = {TIPO_MSG, TIPO_PONG, TIPO_ECHO, TIPO_BYE, TIPO_ERROR}
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
    Levanta ValueError se a mensagem recebida for malformada ou se o buffer
    crescer além de MAX_BUFFER sem encontrar o delimitador (protege a memória
    contra um fluxo malicioso/bugado que nunca envia '\\n').
    """
    while DELIMITADOR.encode() not in buffer:
        pedaco = sock.recv(4096)
        if not pedaco:
            # Outra ponta encerrou a conexão de forma limpa (FIN)
            return None
        buffer.extend(pedaco)

        # Limite de segurança: sem '\n' dentro de MAX_BUFFER, algo está errado.
        # Limpa o buffer para tentar ressincronizar no próximo '\n'.
        if len(buffer) > MAX_BUFFER:
            buffer.clear()
            raise ValueError(
                f"Fluxo sem delimitador {DELIMITADOR!r} além de {MAX_BUFFER} bytes"
            )

    # Extrai uma linha completa (até e incluindo o '\n') e deixa o restante
    # no buffer para a próxima chamada
    indice = buffer.index(DELIMITADOR.encode())
    linha_bytes = bytes(buffer[: indice + 1])
    del buffer[: indice + 1]

    return parsear(linha_bytes.decode("utf-8"))
