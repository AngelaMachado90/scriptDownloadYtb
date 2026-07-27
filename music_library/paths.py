"""Validação de nomes e destinos seguros dentro da biblioteca."""

import unicodedata
from pathlib import Path


def nome_seguro(valor, campo):
    valor = unicodedata.normalize("NFC", valor).strip()
    if not valor or len(valor) > 100 or valor in {".", ".."} or "\x00" in valor:
        raise ValueError(f"{campo} inválido.")
    if any(separador in valor for separador in ("/", "\\")) or Path(valor).name != valor:
        raise ValueError(f"{campo} não pode conter caminhos ou separadores.")
    return valor


def diretorio_do_album(downloads_dir, artista, album):
    destino = (Path(downloads_dir) / artista / album).resolve()
    try:
        destino.relative_to(Path(downloads_dir).resolve())
    except ValueError as erro:
        raise ValueError("Diretório de destino inválido.") from erro
    return destino
