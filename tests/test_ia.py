import pytest

from src.assistant import ia
from src.assistant.ollama import ClienteOllama
from tests.falsos import ServidorFalso, erro_http


def cliente(servidor):
    return ClienteOllama("http://localhost:11434", abrir=servidor)


def ultimo_corpo(servidor):
    return [corpo for caminho, corpo in servidor.pedidos if caminho == "/api/chat"][-1]


def test_resposta_vem_do_texto_do_modelo():
    servidor = ServidorFalso(trechos=["Você gastou ", "muito em Lazer."])
    assert ia.perguntar("Onde gastei mais?", [], "contexto", cliente(servidor)) == "Você gastou muito em Lazer."


def test_contexto_vai_no_system_e_a_pergunta_e_a_ultima_mensagem():
    servidor = ServidorFalso()
    ia.perguntar("  Posso gastar mais?  ", [], "Saldo atual: R$ 100,00", cliente(servidor))

    mensagens = ultimo_corpo(servidor)["messages"]
    assert mensagens[0]["role"] == "system"
    assert "Saldo atual: R$ 100,00" in mensagens[0]["content"]
    assert ia.PROMPT_DO_SISTEMA in mensagens[0]["content"]
    assert mensagens[-1] == {"role": "user", "content": "Posso gastar mais?"}
    assert ultimo_corpo(servidor)["options"]["num_predict"] == ia.MAX_TOKENS


def test_modelo_padrao_e_troca_pelo_env_e_pelo_parametro(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODELO", raising=False)
    servidor = ServidorFalso(modelos=["qwen2.5:3b", "outro:1b", "terceiro:2b"])
    ia.perguntar("oi", [], "", cliente(servidor))
    assert ultimo_corpo(servidor)["model"] == ia.modelos.MODELO_PADRAO

    monkeypatch.setenv("OLLAMA_MODELO", "outro:1b")
    ia.perguntar("oi", [], "", cliente(servidor))
    assert ultimo_corpo(servidor)["model"] == "outro:1b"

    ia.perguntar("oi", [], "", cliente(servidor), modelo="terceiro:2b")
    assert ultimo_corpo(servidor)["model"] == "terceiro:2b"


def test_historico_e_limitado_comeca_pelo_usuario_e_so_leva_role_e_content():
    historico = []
    for i in range(10):
        historico.append({"role": "user", "content": f"pergunta {i}"})
        historico.append({"role": "assistant", "content": f"resposta {i}", "aviso": "extra da tela"})
    servidor = ServidorFalso()

    ia.perguntar("nova", historico, "", cliente(servidor))

    mensagens = ultimo_corpo(servidor)["messages"]
    conversa = mensagens[1:]  # sem o system
    assert len(conversa) <= ia.MAX_MENSAGENS_HISTORICO + 1
    assert conversa[0]["role"] == "user"
    assert conversa[-1]["content"] == "nova"
    assert all(set(m) == {"role", "content"} for m in mensagens)


def test_comeco_da_resposta_sem_quebras_de_linha():
    servidor = ServidorFalso(trechos=["\n\n", "  Olá", "!"])
    assert ia.perguntar("oi", [], "", cliente(servidor)) == "Olá!"


def test_fluxo_devolve_os_trechos_em_ordem():
    servidor = ServidorFalso(trechos=["A", "B", "C"])
    assert list(ia.perguntar_em_fluxo("oi", [], "", cliente(servidor))) == ["A", "B", "C"]


def test_resposta_cortada_avisa_o_usuario():
    servidor = ServidorFalso(trechos=["Texto longo"], motivo_fim="length")
    assert "cortada" in ia.perguntar("oi", [], "", cliente(servidor))


def test_resposta_vazia_vira_erro_amigavel():
    with pytest.raises(ia.IAIndisponivel, match="vazia"):
        ia.perguntar("oi", [], "", cliente(ServidorFalso(trechos=["   "])))


def test_pergunta_vazia_ou_muito_longa_e_recusada():
    with pytest.raises(ValueError):
        ia.perguntar("   ", [], "", cliente(ServidorFalso()))
    with pytest.raises(ValueError):
        ia.perguntar("a" * (ia.LIMITE_PERGUNTA + 1), [], "", cliente(ServidorFalso()))


def test_erros_do_ollama_viram_mensagens_em_portugues():
    with pytest.raises(ia.IAIndisponivel, match="Ollama"):
        ia.perguntar("oi", [], "", cliente(ServidorFalso(offline=True)))
    with pytest.raises(ia.IAIndisponivel, match="ollama pull"):
        ia.perguntar("oi", [], "", cliente(ServidorFalso()), modelo="inexistente:1b")
    with pytest.raises(ia.IAIndisponivel, match="memória"):
        ia.perguntar("oi", [], "", cliente(ServidorFalso(erro_chat=erro_http(500, "requires more system memory"))))


def test_diagnostico_offline():
    assert ia.diagnosticar(cliente(ServidorFalso(offline=True))).estado == "offline"


def test_diagnostico_sem_modelo_baixado():
    diagnostico = ia.diagnosticar(cliente(ServidorFalso(modelos=[])))
    assert diagnostico.estado == "sem_modelo"
    assert diagnostico.versao == "0.99.0"


def test_diagnostico_escolhe_o_modelo_do_env_ou_o_primeiro(monkeypatch):
    servidor = ServidorFalso(modelos=["gemma3:4b", "qwen2.5:3b"])
    monkeypatch.delenv("OLLAMA_MODELO", raising=False)
    assert ia.diagnosticar(cliente(servidor)).modelo_escolhido == "qwen2.5:3b"  # o padrão do app, se instalado

    monkeypatch.setenv("OLLAMA_MODELO", "gemma3:4b")
    assert ia.diagnosticar(cliente(servidor)).modelo_escolhido == "gemma3:4b"

    monkeypatch.setenv("OLLAMA_MODELO", "nao-baixado:7b")
    diagnostico = ia.diagnosticar(cliente(servidor))
    assert diagnostico.estado == "pronto"
    assert diagnostico.modelo_escolhido == "gemma3:4b"  # cai no primeiro instalado


def test_nome_sem_tag_equivale_a_latest(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODELO", "phi3")
    servidor = ServidorFalso(modelos=["gemma3:4b", "phi3:latest"])
    assert ia.diagnosticar(cliente(servidor)).modelo_escolhido == "phi3:latest"


def test_verificar_numeros_aponta_valor_fora_do_resumo():
    assert ia.verificar_numeros("Sobram R$ 999,00", "Saldo: R$ 100,00") == ["R$ 999,00"]
    assert ia.verificar_numeros("Saldo de R$ 100,00", "Saldo: R$ 100,00") == []
