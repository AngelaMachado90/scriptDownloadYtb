"""Resultados e classificação final de operações de download."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResultadoDownload:
    arquivos: list[Path] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)

    def adicionar(self, outro):
        self.arquivos.extend(outro.arquivos)
        self.falhas.extend(outro.falhas)


def status_final(resultado):
    if resultado.arquivos and resultado.falhas:
        return "PARCIAL"
    if resultado.arquivos:
        return "SUCESSO"
    return "FALHA"
