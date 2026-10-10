from types import SimpleNamespace

import pytest

from src.assistant import ia


class ClienteFalso:
    """Imita client.messages.create sem internet: guarda a chamada e devolve uma resposta pronta."""

    def __init__(self, texto="Resposta de teste", stop_reason="end_turn", erro=None):
        self.chamadas = []
        self._resposta = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=texto)], stop_reason=stop_reason
        )
        self._erro = erro
        self.messages = self

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        if self._erro:
            raise self._erro
        return self._resposta


def test_resposta_vem_do_texto_do_cliente():
    cliente = ClienteFalso("Você gastou muito em Lazer.")
    assert ia.perguntar("Onde gastei mais?", [], "contexto", cliente) == "Você gastou muito em Lazer."


def test_contexto_vai_no_system_e_a_pergunta_e_a_ultima_mensagem():
    cliente = ClienteFalso()
    ia.perguntar("  Posso gastar mais?  ", [], "Saldo atual: R$ 100,00", cliente)

    chamada = cliente.chamadas[0]
    assert "Saldo atual: R$ 100,00" in chamada["system"]
    assert ia.PROMPT_DO_SISTEMA in chamada["system"]
    assert chamada["messages"][-1] == {"role": "user", "content": "Posso gastar mais?"}
    assert chamada["max_tokens"] == ia.MAX_TOKENS


def test_modelo_padrao_e_troca_pelo_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    cliente = ClienteFalso()
    ia.perguntar("oi", [], "", cliente)
    assert cliente.chamadas[0]["model"] == ia.MODELO_PADRAO

    monkeypatch.setenv("ANTHROPIC_MODEL", "outro-modelo")
    ia.perguntar("oi", [], "", cliente)
    assert cliente.chamadas[1]["model"] == "outro-modelo"


def test_historico_e_limitado_e_comeca_por_mensagem_do_usuario():
    historico = []
    for i in range(10):
        historico.append({"role": "user", "content": f"pergunta {i}"})
        historico.append({"role": "assistant", "content": f"resposta {i}"})
    cliente = ClienteFalso()

    ia.perguntar("nova", historico, "", cliente)

    mensagens = cliente.chamadas[0]["messages"]
    assert len(mensagens) <= ia.MAX_MENSAGENS_HISTORICO + 1
    assert mensagens[0]["role"] == "user"
    assert mensagens[-1]["content"] == "nova"


def test_varios_blocos_de_texto_sao_juntados():
    cliente = ClienteFalso()
    cliente._resposta = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Parte 1. "),
            SimpleNamespace(type="tool_use", text="ignorado"),
            SimpleNamespace(type="text", text="Parte 2."),
        ],
        stop_reason="end_turn",
    )
    assert ia.perguntar("oi", [], "", cliente) == "Parte 1. Parte 2."


def test_resposta_cortada_avisa_o_usuario():
    cliente = ClienteFalso("Texto longo", stop_reason="max_tokens")
    assert "cortada" in ia.perguntar("oi", [], "", cliente)


def test_resposta_vazia_vira_erro_amigavel():
    cliente = ClienteFalso("   ")
    with pytest.raises(ia.IAIndisponivel):
        ia.perguntar("oi", [], "", cliente)


def test_pergunta_vazia_ou_muito_longa_e_recusada():
    with pytest.raises(ValueError):
        ia.perguntar("   ", [], "", ClienteFalso())
    with pytest.raises(ValueError):
        ia.perguntar("a" * (ia.LIMITE_PERGUNTA + 1), [], "", ClienteFalso())


def test_erros_da_api_viram_mensagens_em_portugues():
    class AuthenticationError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class APITimeoutError(APIConnectionError):  # igual ao SDK: o timeout é um tipo de erro de conexão
        pass

    with pytest.raises(ia.IAIndisponivel, match="chave"):
        ia.perguntar("oi", [], "", ClienteFalso(erro=AuthenticationError("401")))
    with pytest.raises(ia.IAIndisponivel, match="conexão"):
        ia.perguntar("oi", [], "", ClienteFalso(erro=APITimeoutError("demorou")))


def test_falta_de_creditos_tem_mensagem_propria():
    erro = Exception("Your credit balance is too low to access the API")
    with pytest.raises(ia.IAIndisponivel, match="créditos"):
        ia.perguntar("oi", [], "", ClienteFalso(erro=erro))


def test_sem_chave_no_env_a_ia_fica_indisponivel(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ia.chave_configurada() is False
    with pytest.raises(ia.IAIndisponivel, match="ANTHROPIC_API_KEY"):
        ia.perguntar("oi", [], "")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-teste")
    assert ia.chave_configurada() is True