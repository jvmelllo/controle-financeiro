import urllib.error

import pytest

from src.assistant.ollama import (
    ClienteOllama, ModeloNaoInstalado, OllamaErro, OllamaOffline, endereco_do_servidor,
)
from tests.falsos import ServidorFalso, erro_http

MENSAGENS = [{"role": "user", "content": "oi"}]


def cliente(servidor):
    return ClienteOllama("http://localhost:11434", abrir=servidor)


def test_endereco_padrao_e_variavel_de_ambiente(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert endereco_do_servidor() == "http://localhost:11434"
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:12345")
    assert endereco_do_servidor() == "http://127.0.0.1:12345"
    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0:11434")
    assert endereco_do_servidor() == "http://localhost:11434"
    monkeypatch.setenv("OLLAMA_HOST", "https://meu-servidor/")
    assert endereco_do_servidor() == "https://meu-servidor"


def test_versao_e_disponibilidade():
    assert cliente(ServidorFalso()).versao() == "0.99.0"
    assert cliente(ServidorFalso()).disponivel() is True
    assert cliente(ServidorFalso(offline=True)).versao() is None
    assert cliente(ServidorFalso(offline=True)).disponivel() is False


def test_lista_de_modelos_vem_ordenada_com_detalhes():
    modelos = cliente(ServidorFalso(modelos=["qwen2.5:3b", "llama3.2:3b"])).listar_modelos()
    assert [m.nome for m in modelos] == ["llama3.2:3b", "qwen2.5:3b"]
    assert modelos[0].parametros == "3B"
    assert modelos[0].quantizacao == "Q4_K_M"
    assert modelos[0].tamanho_gb == pytest.approx(1.9)


def test_lista_de_modelos_com_servidor_desligado_avisa_em_portugues():
    with pytest.raises(OllamaOffline, match="Ollama"):
        cliente(ServidorFalso(offline=True)).listar_modelos()


def test_resposta_chega_em_pedacos_e_o_ultimo_traz_o_motivo_do_fim():
    pedacos = list(cliente(ServidorFalso()).conversar_em_fluxo("qwen2.5:3b", MENSAGENS))
    assert [p.texto for p in pedacos] == ["Olá", ", tudo bem.", ""]
    assert [p.motivo_fim for p in pedacos] == [None, None, "stop"]


def test_conversar_junta_tudo():
    assert cliente(ServidorFalso()).conversar("qwen2.5:3b", MENSAGENS) == ("Olá, tudo bem.", "stop")


def test_pedido_leva_modelo_mensagens_e_opcoes():
    servidor = ServidorFalso()
    cliente(servidor).conversar("qwen2.5:3b", MENSAGENS, temperatura=0.1, max_tokens=50)
    caminho, corpo = servidor.pedidos[-1]
    assert caminho == "/api/chat"
    assert corpo["model"] == "qwen2.5:3b"
    assert corpo["messages"] == MENSAGENS
    assert corpo["stream"] is True
    assert corpo["options"]["temperature"] == 0.1
    assert corpo["options"]["num_predict"] == 50


def test_modelo_nao_instalado_ensina_o_comando():
    with pytest.raises(ModeloNaoInstalado, match="ollama pull llama3.2:3b"):
        cliente(ServidorFalso()).conversar("llama3.2:3b", MENSAGENS)


def test_falta_de_memoria_vira_mensagem_clara():
    servidor = ServidorFalso(erro_chat=erro_http(500, "model requires more system memory (8.0 GiB)"))
    with pytest.raises(OllamaErro, match="memória"):
        cliente(servidor).conversar("qwen2.5:3b", MENSAGENS)


def test_outro_erro_http_mostra_o_detalhe():
    with pytest.raises(OllamaErro, match="boom"):
        cliente(ServidorFalso(erro_chat=erro_http(500, "boom"))).conversar("qwen2.5:3b", MENSAGENS)


def test_servidor_desligado_na_conversa():
    with pytest.raises(OllamaOffline):
        cliente(ServidorFalso(offline=True)).conversar("qwen2.5:3b", MENSAGENS)


def test_erro_no_meio_do_fluxo_e_linha_ilegivel():
    com_erro = ServidorFalso(linhas_extras=['{"error": "falhou no meio"}'])
    with pytest.raises(OllamaErro, match="falhou no meio"):
        cliente(com_erro).conversar("qwen2.5:3b", MENSAGENS)
    ilegivel = ServidorFalso(linhas_extras=["isto não é json"])
    with pytest.raises(OllamaErro, match="ilegível"):
        cliente(ilegivel).conversar("qwen2.5:3b", MENSAGENS)


def test_timeout_no_meio_da_resposta_vira_erro_amigavel():
    class Lenta:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            raise TimeoutError("sem resposta")

    with pytest.raises(OllamaErro, match="demorou"):
        cliente(lambda req, timeout=None: Lenta()).conversar("qwen2.5:3b", MENSAGENS)
