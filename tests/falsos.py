"""Servidor Ollama falso para os testes: responde como a API real, sem rede e sem instalar nada."""

import io
import json
import urllib.error
from urllib.parse import urlparse


class RespostaFalsa:
    def __init__(self, linhas: list[bytes]):
        self._linhas = linhas

    def read(self) -> bytes:
        return b"".join(self._linhas)

    def __iter__(self):
        return iter(self._linhas)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _json(dado: dict) -> RespostaFalsa:
    return RespostaFalsa([json.dumps(dado).encode("utf-8")])


def _erro_http(codigo: int, mensagem: str) -> urllib.error.HTTPError:
    corpo = io.BytesIO(json.dumps({"error": mensagem}).encode("utf-8"))
    return urllib.error.HTTPError("http://localhost:11434", codigo, mensagem, {}, corpo)


class ServidorFalso:
    """Use como `abrir=` do ClienteOllama. Guarda cada pedido em `pedidos` (caminho, corpo)."""

    def __init__(self, modelos=("qwen2.5:3b",), trechos=("Olá", ", tudo bem."), motivo_fim="stop",
                 offline=False, erro_chat=None, linhas_extras=()):
        self.modelos = list(modelos)
        self.trechos = list(trechos)
        self.motivo_fim = motivo_fim
        self.offline = offline
        self.erro_chat = erro_chat  # urllib.error.HTTPError a levantar no /api/chat
        self.linhas_extras = list(linhas_extras)  # linhas cruas antes do 'done' (para testar erros)
        self.pedidos: list[tuple[str, dict | None]] = []

    def __call__(self, requisicao, timeout=None):
        if self.offline:
            raise urllib.error.URLError("conexão recusada")
        caminho = urlparse(requisicao.full_url).path
        corpo = json.loads(requisicao.data) if requisicao.data else None
        self.pedidos.append((caminho, corpo))

        if caminho == "/api/version":
            return _json({"version": "0.99.0"})
        if caminho == "/api/tags":
            return _json({"models": [
                {"name": m, "size": 1_900_000_000, "details": {"parameter_size": "3B", "quantization_level": "Q4_K_M"}}
                for m in self.modelos
            ]})
        if caminho == "/api/chat":
            if self.erro_chat:
                raise self.erro_chat
            if corpo["model"] not in self.modelos:
                raise _erro_http(404, f"model '{corpo['model']}' not found")
            linhas = [(json.dumps({"message": {"role": "assistant", "content": t}, "done": False}) + "\n").encode()
                      for t in self.trechos]
            linhas += [(linha + "\n").encode() for linha in self.linhas_extras]
            linhas.append((json.dumps({"message": {"role": "assistant", "content": ""}, "done": True,
                                       "done_reason": self.motivo_fim}) + "\n").encode())
            return RespostaFalsa(linhas)
        raise _erro_http(404, "not found")


def erro_http(codigo: int, mensagem: str) -> urllib.error.HTTPError:
    return _erro_http(codigo, mensagem)
