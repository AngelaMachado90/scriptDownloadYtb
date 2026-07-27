"""Leitura não destrutiva da biblioteca local."""

import re
import unicodedata
from collections import Counter
from pathlib import Path

from .catalog import CATALOGO


def normalizar_faixa(nome):
    texto = unicodedata.normalize("NFKD", Path(nome).stem).encode("ascii", "ignore").decode().lower()
    texto = re.sub(r"^\s*\d{1,3}\s*[-._]\s*", "", texto)
    texto = re.sub(r"(?i)^disturbed\s*-?\s*", "", texto)
    texto = re.sub(r"(?i)\s*\[?official\s+(music|lyrics)\s+video\]?\s*$", "", texto)
    return re.sub(r"[^a-z0-9]+", "", texto)


def catalogo_do_album(artista, album):
    return next((item for item in CATALOGO if item["artista"] == artista and item["album"] == album), None)


def avaliar_album(artista, album, diretorio):
    catalogo = catalogo_do_album(artista, album)
    arquivos = sorted(Path(diretorio).rglob("*.mp3")) if Path(diretorio).exists() else []
    if not catalogo:
        return {"Artista": artista, "CD": album, "Progresso": "—", "Status": "Sem catálogo", "faltantes": [], "extras": [], "duplicatas": []}
    esperadas = [normalizar_faixa(faixa) for faixa in catalogo["faixas"]]
    existentes = [normalizar_faixa(arquivo.name) for arquivo in arquivos]
    contagem = Counter(existentes)
    faltantes = [faixa for faixa, normalizada in zip(catalogo["faixas"], esperadas) if contagem[normalizada] == 0]
    extras = [arquivo.name for arquivo, normalizada in zip(arquivos, existentes) if normalizada not in esperadas]
    duplicatas = [faixa for faixa, quantidade in contagem.items() if quantidade > 1 and faixa in esperadas]
    progresso = len(esperadas) - len(faltantes)
    if not arquivos:
        status = "Sem faixas"
    elif not faltantes and not extras and not duplicatas:
        status = "Completo"
    else:
        status = "Incompleto"
    return {"Artista": artista, "CD": album, "Progresso": f"{progresso} / {len(esperadas)}", "Status": status, "faltantes": faltantes, "extras": extras, "duplicatas": duplicatas}


def listar_biblioteca(downloads_dir):
    raiz = Path(downloads_dir)
    registros = []
    for artista_dir in sorted((p for p in raiz.iterdir() if p.is_dir()), key=lambda p: p.name) if raiz.exists() else []:
        albuns = sorted((p for p in artista_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
        for album in albuns:
            registros.append(avaliar_album(artista_dir.name, album.name, album))
    return registros


def filtrar_biblioteca(registros, artista="Todos os artistas", cd="Todos os CDs"):
    return [registro for registro in registros if (artista == "Todos os artistas" or registro["Artista"] == artista) and (cd == "Todos os CDs" or registro["CD"] == cd)]
