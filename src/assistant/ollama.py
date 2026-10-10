"""Cliente mínimo da API local do Ollama.

Usa só a biblioteca padrão (nenhuma dependência nova). O Ollama roda no próprio computador
(por padrão em http://localhost:11434), então nenhum dado sai da máquina.

Os testes passam a função `abrir` (no lugar de urllib.request.urlopen) para simular o servidor,
sem precisar do Ollama instalado.
"""

import json
import os
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass

HOST_PADRAO = "http://localhost:11434"
TIMEOUT_CONSULTA = 5  # segundos: perguntas rápidas ao servidor (versão, lista de modelos)
TIMEOUT_RESPOSTA = 300  # segundos sem receber nada: a 1ª pergunta carrega o modelo na memória
MANTER_NA_MEMORIA = "10m"  # o modelo fica carregado entre uma pergunta e outra


class OllamaErro(Exception):
    """Falha ao falar com o Ollama; a mensagem já é própria para mostrar ao usuário."""


class OllamaOffline(OllamaErro):
    """O servidor do Ollama não está respondendo."""


class ModeloNaoInstalado(OllamaErro):
    """O modelo pedido ainda não foi baixado."""


@dataclass(frozen=True)
class ModeloInstalado:
    nome: str
    tamanho_bytes: int = 0
    parametros: str = ""  # ex.: "3.1B"
    quantizacao: str = ""  # ex.: "Q4_K_M"

    @property
    def tamanho_gb(self) -> float:
        return self.tamanho_bytes / 1_000_000_000


@dataclass(frozen=True)
class Pedaco:
    """Um trecho da resposta. O último vem com `motivo_fim` ('stop' = terminou, 'length' = cortada)."""

    texto: str
    motivo_fim: str | None = None


def endereco_do_servidor() -> str:
    """Lê OLLAMA_HOST (o mesmo nome que o próprio Ollama usa) e devolve uma URL completa."""
    bruto = os.environ.get("OLLAMA_HOST", "").strip() or HOST_PADRAO
    if "://" not in bruto:
        bruto = "http://" + bruto
    bruto = bruto.rstrip("/")
    # 0.0.0.0 serve para o servidor escutar; para conectar, o endereço é o local
    return bruto.replace("//0.0.0.0", "//localhost", 1)


def _mensagem_do_erro_http(erro: urllib.error.HTTPError) -> str:
    try:
        return str(json.loads(erro.read().decode("utf-8")).get("error", "")).strip()
    except (ValueError, OSError):
        return ""


class ClienteOllama:
    def __init__(self, endereco: str | None = None, abrir: Callable | None = None):
        self.endereco = (endereco or endereco_do_servidor()).rstrip("/")
        self._abrir = abrir or urllib.request.urlopen

    # ---------- baixo nível ----------
    def _requisitar(self, caminho: str, corpo: dict | None = None, timeout: float = TIMEOUT_CONSULTA):
        dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
        requisicao = urllib.request.Request(
            self.endereco + caminho,
            data=dados,
            headers={"Content-Type": "application/json"},
            method="GET" if corpo is None else "POST",
        )
        try:
            return self._abrir(requisicao, timeout=timeout)
        except urllib.error.HTTPError as erro:  # HTTPError é filha de URLError: vem primeiro
            raise self._erro_http(erro, (corpo or {}).get("model", "")) from erro
        except (urllib.error.URLError, ConnectionError, TimeoutError, socket.timeout) as erro:
            raise OllamaOffline(
                f"Não encontrei o Ollama em {self.endereco}. Abra o aplicativo Ollama "
                "(ou rode `ollama serve` em outro terminal) e tente de novo."
            ) from erro

    @staticmethod
    def _erro_http(erro: urllib.error.HTTPError, modelo: str) -> OllamaErro:
        detalhe = _mensagem_do_erro_http(erro)
        if erro.code == 404:
            nome = modelo or "o modelo"
            return ModeloNaoInstalado(
                f"O modelo '{nome}' não está instalado. Baixe com: ollama pull {nome}"
            )
        if "memory" in detalhe.lower():
            return OllamaErro(
                "O computador não tem memória suficiente para este modelo. "
                "Escolha um modelo menor (veja a lista na tela do assistente)."
            )
        return OllamaErro(f"O Ollama recusou o pedido ({erro.code}). {detalhe}".strip())

    # ---------- consultas ----------
    def versao(self) -> str | None:
        """Versão do servidor, ou None se ele não estiver respondendo."""
        try:
            with self._requisitar("/api/version") as resposta:
                return str(json.loads(resposta.read().decode("utf-8")).get("version", "")) or None
        except (OllamaErro, ValueError):
            return None

    def disponivel(self) -> bool:
        return self.versao() is not None

    def listar_modelos(self) -> list[ModeloInstalado]:
        with self._requisitar("/api/tags") as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        modelos = []
        for item in dados.get("models", []):
            detalhes = item.get("details") or {}
            modelos.append(ModeloInstalado(
                nome=item.get("name") or item.get("model", ""),
                tamanho_bytes=int(item.get("size") or 0),
                parametros=detalhes.get("parameter_size", ""),
                quantizacao=detalhes.get("quantization_level", ""),
            ))
        return sorted(modelos, key=lambda m: m.nome)

    # ---------- conversa ----------
    def conversar_em_fluxo(
        self, modelo: str, mensagens: list[dict], temperatura: float = 0.2,
        max_tokens: int = 700, contexto_tokens: int = 4096,
    ) -> Iterator[Pedaco]:
        """Envia a conversa e devolve a resposta aos poucos (o Ollama manda um JSON por linha)."""
        corpo = {
            "model": modelo,
            "messages": mensagens,
            "stream": True,
            "keep_alive": MANTER_NA_MEMORIA,
            "options": {
                "temperature": temperatura,
                "num_predict": max_tokens,
                "num_ctx": contexto_tokens,
            },
        }
        with self._requisitar("/api/chat", corpo, timeout=TIMEOUT_RESPOSTA) as resposta:
            try:
                for linha in resposta:
                    if not linha.strip():
                        continue
                    try:
                        evento = json.loads(linha.decode("utf-8"))
                    except ValueError as erro:
                        raise OllamaErro("O Ollama enviou uma resposta ilegível.") from erro
                    if evento.get("error"):
                        raise OllamaErro(f"O Ollama não conseguiu responder: {evento['error']}")
                    texto = (evento.get("message") or {}).get("content", "")
                    if evento.get("done"):
                        yield Pedaco(texto, evento.get("done_reason") or "stop")
                        return
                    if texto:
                        yield Pedaco(texto)
            except (TimeoutError, socket.timeout) as erro:
                raise OllamaErro(
                    "O modelo demorou demais para responder. Tente um modelo menor ou "
                    "uma pergunta mais curta."
                ) from erro

    def conversar(self, modelo: str, mensagens: list[dict], **opcoes) -> tuple[str, str | None]:
        """Versão sem 'aos poucos': devolve (texto completo, motivo do fim)."""
        partes, motivo = [], None
        for pedaco in self.conversar_em_fluxo(modelo, mensagens, **opcoes):
            partes.append(pedaco.texto)
            motivo = pedaco.motivo_fim or motivo
        return "".join(partes), motivo
