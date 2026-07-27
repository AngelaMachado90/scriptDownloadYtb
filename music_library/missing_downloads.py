"""Planeja e executa, somente após confirmação, faixas faltantes catalogadas."""

from pathlib import Path

from .album_sources import best_album_source
from .library import avaliar_album, catalogo_do_album, normalizar_faixa
from .track_sources import best_source


def acao_faltantes_disponivel(registro):
    """A interface só oferece a ação para um CD efetivamente incompleto."""
    return registro.get("Status") == "Incompleto" and bool(registro.get("faltantes"))


def planejar_faixas_faltantes(artist, album, directory, history=None):
    avaliacao = avaliar_album(artist, album, directory)
    if avaliacao["Status"] != "Incompleto":
        return []
    catalogo = catalogo_do_album(artist, album)
    playlist = best_album_source(artist, album)
    plano = []
    for indice, faixa in enumerate(catalogo["faixas"], 1):
        if faixa not in avaliacao["faltantes"]:
            continue
        individual = best_source(artist, album, faixa, history)
        if individual:
            plano.append({"artist": artist, "album": album, "track": faixa, "index": indice, "url": individual["url"], "kind": "individual", "candidate_id": individual.get("candidate_id")})
        elif playlist:
            candidate_id = None
            if history:
                candidate_id = history.add_candidate(artist, album, faixa, playlist["url"], "CATALOGO_OFICIAL")
                if not history.can_attempt(candidate_id):
                    continue
            plano.append({"artist": artist, "album": album, "track": faixa, "index": indice, "url": playlist["url"], "kind": "playlist_item", "candidate_id": candidate_id})
    return plano


def executar_plano(plano, destination, download_one, history=None):
    """Executa uma fonte por vez; `download_one` é injetável para testes."""
    resultado = {"baixadas": [], "faltando": [], "falhas": [], "alternativas": []}
    for item in plano:
        existentes = {normalizar_faixa(path.name) for path in Path(destination).glob("*.mp3")}
        if normalizar_faixa(item["track"]) in existentes:
            continue
        retorno = download_one(item, destination)
        if retorno.arquivos and not retorno.falhas:
            resultado["baixadas"].append(item["track"])
            if history and item["candidate_id"]:
                history.record_attempt(item["candidate_id"], "SUCESSO", "UNKNOWN", "Download concluído.")
            if history:
                history.record_download(item["artist"], item["album"], item["track"], item["url"])
        else:
            resultado["faltando"].append(item["track"])
            mensagem = retorno.falhas[-1] if retorno.falhas else "Não foi possível baixar esta fonte."
            resultado["falhas"].append(mensagem)
            if history and item["candidate_id"]:
                history.record_attempt(item["candidate_id"], "FALHA", "UNKNOWN", mensagem, technical_message="Falha técnica registrada no arquivo de log.")
                for fonte in history.sources(item["artist"], item["album"], item["track"]):
                    if fonte["id"] != item["candidate_id"] and history.can_attempt(fonte["id"]):
                        resultado["alternativas"].append(item["track"])
                        break
    return resultado
