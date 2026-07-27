"""Fontes versionadas por faixa; nenhuma busca ou validação automática."""

import json
from pathlib import Path

from .history import normalizar_url_youtube


PATH = Path(__file__).resolve().parent.parent / "data" / "track_sources.json"


def sources_for_track(artist, album, title, path=PATH):
    sources = json.loads(Path(path).read_text(encoding="utf-8"))["sources"]
    selecionadas = []
    video_ids = set()
    for source in sorted((source for source in sources if source["artist"] == artist and source["album"] == album and source["title"] == title), key=lambda source: source["priority"]):
        normalizada = normalizar_url_youtube(source["url"])
        video_id = normalizada.rsplit("=", 1)[-1]
        if video_id in video_ids:
            continue
        video_ids.add(video_id)
        selecionadas.append(source | {"url": normalizada, "video_id": video_id, "status": source.get("status", "ATIVA")})
    return selecionadas


def best_source(artist, album, title, history=None, now=None):
    for source in sources_for_track(artist, album, title):
        if history is None:
            return source
        candidate = history.add_candidate(artist, album, title, source["url"], "CATALOGO_OFICIAL", source["priority"], source.get("origin", ""), source.get("status", "ATIVA"))
        if history.can_attempt(candidate, now):
            return source | {"candidate_id": candidate}
    return None
