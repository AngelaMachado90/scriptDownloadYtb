"""Fontes oficiais versionadas, sem coleta automática de URLs."""

import json
from pathlib import Path
from urllib.parse import quote_plus


CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "official_artists.json"


def artistas_oficiais(path=CONFIG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))["artists"]


def artista_oficial(nome, path=CONFIG_PATH):
    return next((artista for artista in artistas_oficiais(path) if artista["canonical_name"] == nome), None)


def busca_oficial(nome, faixa, path=CONFIG_PATH):
    artista = artista_oficial(nome, path)
    termo = (artista or {"search_terms": ["{artista} {faixa} official audio"]})["search_terms"][0]
    return "https://www.youtube.com/results?search_query=" + quote_plus(termo.format(artista=nome, faixa=faixa))


def url_pertence_ao_canal(url, nome, path=CONFIG_PATH):
    artista = artista_oficial(nome, path)
    return bool(artista and (url.startswith(artista["youtube_channel"]) or artista["youtube_channel"].rsplit("/", 1)[-1] in url))
