"""Validação sem download do ambiente yt-dlp para desafios JavaScript."""

import argparse
import sys
from pathlib import Path

import yt_dlp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music_library.downloader import opcoes_desafio_javascript, validar_recursos_desafio


def main():
    parser = argparse.ArgumentParser(description="Extrai metadados do YouTube sem baixar arquivos.")
    parser.add_argument("url", help="URL do vídeo Voices a validar")
    args = parser.parse_args()

    diagnosticos = validar_recursos_desafio(exigir_cookies=True)
    if diagnosticos:
        print("Diagnóstico de pré-requisitos:")
        print("\n".join(f"- {item}" for item in diagnosticos))
        return 1

    opcoes = opcoes_desafio_javascript() | {"quiet": True, "skip_download": True, "simulate": True}
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(args.url, download=False)
    except Exception as erro:
        print(f"Falha na extração sem download: {erro}")
        return 1

    formatos = info.get("formats") or []
    audio = [formato for formato in formatos if formato.get("acodec") not in {None, "none"}]
    if not audio:
        print("Nenhum formato com áudio foi encontrado.")
        return 1
    print(f"Metadados extraídos com sucesso. Formatos de áudio disponíveis: {len(audio)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
