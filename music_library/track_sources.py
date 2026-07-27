"""Fontes versionadas por faixa; nenhuma busca ou validação automática."""

import json
from pathlib import Path


PATH = Path(__file__).resolve().parent.parent / "data" / "track_sources.json"


def sources_for_track(artist, album, title, path=PATH):
    sources = json.loads(Path(path).read_text(encoding="utf-8"))["sources"]
    return sorted((source for source in sources if source["artist"] == artist and source["album"] == album and source["title"] == title), key=lambda source: source["priority"])


def best_source(artist, album, title, history=None, now=None):
    for source in sources_for_track(artist, album, title):
        if history is None:
            return source
        candidate = history.add_candidate(artist, album, title, source["url"], "CATALOGO_OFICIAL")
        if history.can_attempt(candidate, now):
            return source | {"candidate_id": candidate}
    return None
