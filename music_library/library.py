"""Leitura não destrutiva da biblioteca local."""

from pathlib import Path


def listar_biblioteca(downloads_dir):
    raiz = Path(downloads_dir)
    registros = []
    for artista_dir in sorted((p for p in raiz.iterdir() if p.is_dir()), key=lambda p: p.name) if raiz.exists() else []:
        albuns = sorted((p for p in artista_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
        for album in albuns:
            registros.append({"Artista": artista_dir.name, "Álbum": album.name, "MP3s": sum(1 for f in album.rglob("*.mp3") if f.is_file())})
    return registros
