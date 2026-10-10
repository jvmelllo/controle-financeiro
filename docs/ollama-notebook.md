# Chat com IA local (Ollama) no notebook

Notebook: Aspire AG15-71P, i7 de 13ª geração, 8 GB de RAM (5200 MHz), SSD NVMe, sem placa de vídeo dedicada.

## Modelo indicado

`qwen2.5:3b` (download de cerca de 2 GB). É o modelo que a tela do Assistente recomenda para 8 GB de RAM.

- O NVMe acelera o carregamento do modelo na primeira pergunta; a RAM rápida ajuda na geração do texto.
- Sem placa de vídeo, o modelo roda no processador: funciona, mas é mais lento. A primeira pergunta é a mais demorada.
- Não use modelos maiores (`qwen2.5:7b`, `llama3.1:8b`): não cabem em 8 GB.

## Instalação

No PowerShell:

```
winget install Ollama.Ollama
ollama pull qwen2.5:3b
```

Depois abra o aplicativo Ollama e inicie o app (`streamlit run app.py`). A tela do Assistente confere se o Ollama está aberto e se há modelo baixado.

## Dicas para a memória não apertar

- Feche o navegador pesado e outros programas enquanto usa o chat (o Windows já usa uns 3 a 4 GB).
- Se travar ou der erro de memória, troque para um modelo menor: `ollama pull llama3.2:1b` e defina `OLLAMA_MODELO=llama3.2:1b` no `.env`.

## Para usar o projeto no notebook

O projeto precisa estar no notebook (Git ou pendrive), junto com o `.env` e o banco MySQL.

## Depois de testar

Anotar o tempo de resposta e a qualidade das respostas, para ajustar o prompt ou o modelo.
