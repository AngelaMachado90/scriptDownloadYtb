"""Fontes oficiais versionadas de playlists de álbum, sem execução automática."""

import json
from pathlib import Path


PATH = Path(__file__).resolve().parent.parent / "data" / "album_sources.json"


def album_sources(path=PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))["sources"]


def artists_with_album_sources(path=PATH):
    return sorted({source["artist"] for source in album_sources(path)})


def albums_for_artist(artist, path=PATH):
    return sorted(source["album"] for source in album_sources(path) if source["artist"] == artist)


def best_album_source(artist, album, path=PATH):
    matches = [source for source in album_sources(path) if source["artist"] == artist and source["album"] == album]
    return min(matches, key=lambda source: source["priority"]) if matches else None
