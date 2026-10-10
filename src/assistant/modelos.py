"""Catálogo de modelos do Ollama que cabem em um computador comum.

Os tamanhos são aproximados. A regra prática usada em `recomendar`: o modelo precisa de uns
2 a 3 GB de memória livre além do próprio tamanho para a conversa; por isso a coluna
`ram_minima_gb` é folgada (8 GB para modelos de 3-4B, 16 GB para os de 7-8B).
"""

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ModeloSugerido:
    nome: str  # exatamente como vai no `ollama pull`
    download_gb: float
    ram_minima_gb: int
    descricao: str
    destaque: bool = False  # candidato a "recomendado para o seu computador"


CATALOGO = [
    ModeloSugerido("qwen2.5:3b", 1.9, 8, "Leve e rápido. Boa escolha para começar e para notebook sem placa de vídeo.", True),
    ModeloSugerido("llama3.2:3b", 2.0, 8, "Leve, bom para conversas curtas."),
    ModeloSugerido("gemma3:4b", 3.3, 8, "Multilíngue, respostas mais cuidadosas; um pouco mais lento."),
    ModeloSugerido("qwen2.5:7b", 4.7, 16, "Mais preciso com números e português; exige 16 GB de RAM.", True),
    ModeloSugerido("llama3.1:8b", 4.9, 16, "O mais completo da lista; exige 16 GB de RAM e é o mais lento."),
]
MODELO_PADRAO = CATALOGO[0].nome


def comando_de_instalacao(nome: str) -> str:
    return f"ollama pull {nome}"


def memoria_ram_gb() -> float | None:
    """RAM total do computador em GB, ou None se não der para descobrir (usa só a biblioteca padrão)."""
    try:
        if sys.platform == "win32":
            import ctypes

            class _Memoria(ctypes.Structure):
                _fields_ = [
                    ("tamanho", ctypes.c_ulong), ("em_uso", ctypes.c_ulong),
                    ("total_fisica", ctypes.c_ulonglong), ("livre_fisica", ctypes.c_ulonglong),
                    ("total_arquivo", ctypes.c_ulonglong), ("livre_arquivo", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("livre_virtual", ctypes.c_ulonglong),
                    ("livre_extendida", ctypes.c_ulonglong),
                ]

            estado = _Memoria()
            estado.tamanho = ctypes.sizeof(_Memoria)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
                return estado.total_fisica / 1024**3
            return None
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (OSError, ValueError, AttributeError):
        pass
    return None


def recomendar(ram_gb: float | None) -> ModeloSugerido:
    """O melhor modelo em destaque que cabe na RAM informada; sem informação, o mais leve."""
    destaques = [m for m in CATALOGO if m.destaque]
    if ram_gb is None:
        return destaques[0]
    cabem = [m for m in destaques if m.ram_minima_gb <= ram_gb + 0.5]  # RAM "de 8 GB" aparece como ~7,8
    return cabem[-1] if cabem else destaques[0]
