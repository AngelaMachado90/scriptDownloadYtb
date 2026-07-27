"""Planeja e executa, somente após confirmação, faixas faltantes catalogadas."""

from pathlib import Path

from .album_sources import best_album_source
from .library import avaliar_album, catalogo_do_album, normalizar_faixa
from .track_sources import best_source, sources_for_track


def acao_faltantes_disponivel(registro):
    """A interface só oferece a ação para um CD efetivamente incompleto."""
    return registro.get("Status") == "Incompleto" and bool(registro.get("faltantes"))


def acao_por_cd(registro, tem_catalogo, tem_fonte):
    """Define o único botão permitido para cada linha da biblioteca."""
    status = registro.get("Status")
    if status == "Completo":
        return {"tipo": "completo", "texto": "CD completo", "desabilitado": True}
    if status == "Sem faixas" and tem_catalogo and tem_fonte:
        return {"tipo": "album", "texto": "Baixar CD completo", "desabilitado": False}
    if status == "Incompleto" and registro.get("faltantes") and tem_fonte:
        return {"tipo": "faltantes", "texto": f"Baixar músicas faltantes ({len(registro.get('faltantes', []))})", "desabilitado": False}
    if status == "Incompleto":
        return {"tipo": "sem_faltantes", "texto": "Sem faixas faltantes", "desabilitado": True}
    return {"tipo": "sem_fonte", "texto": "Fonte do CD não cadastrada", "desabilitado": True}


def fontes_candidatas(artist, album, track, history=None, now=None):
    """Retorna URLs únicas, por prioridade, excluindo somente a fonte bloqueada."""
    candidatas = []
    urls = set()
    for source in sources_for_track(artist, album, track):
        candidate_id = None
        if history:
            candidate_id = history.add_candidate(artist, album, track, source["url"], "CATALOGO_OFICIAL", source["priority"], source.get("origin", ""), source.get("status", "ATIVA"))
            if not history.can_attempt(candidate_id, now):
                continue
        if source["url"] not in urls:
            urls.add(source["url"])
            candidatas.append(source | {"candidate_id": candidate_id})
    if history:
        for source in history.sources(artist, album, track):
            if source["url"] not in urls and history.can_attempt(source["id"], now):
                urls.add(source["url"])
                candidatas.append(dict(source) | {"candidate_id": source["id"]})
    return candidatas


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
        candidatas = fontes_candidatas(artist, album, faixa, history)
        if candidatas:
            primeira = candidatas[0]
            plano.append({"artist": artist, "album": album, "track": faixa, "index": indice, "url": primeira["url"], "kind": "individual", "candidate_id": primeira.get("candidate_id"), "sources": candidatas})
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
        fontes = item.get("sources", [item])
        baixou = False
        for fonte in fontes:
            tentativa = item | {"url": fonte["url"], "candidate_id": fonte.get("candidate_id")}
            retorno = download_one(tentativa, destination)
            if retorno.arquivos and not retorno.falhas:
                resultado["baixadas"].append(item["track"])
                if history and tentativa["candidate_id"]:
                    history.record_attempt(tentativa["candidate_id"], "SUCESSO", "UNKNOWN", "Download concluído.")
                    history.record_download(item["artist"], item["album"], item["track"], tentativa["url"])
                baixou = True
                break
            mensagem = retorno.falhas[-1] if retorno.falhas else "Não foi possível baixar esta fonte."
            if history and tentativa["candidate_id"]:
                history.record_attempt(tentativa["candidate_id"], "FALHA", "UNKNOWN", mensagem, technical_message="Falha técnica registrada no arquivo de log.")
        if not baixou:
            resultado["faltando"].append(item["track"])
            resultado["falhas"].append("Não foi possível baixar esta música pelas fontes cadastradas. Tente adicionar outra URL.")
    return resultado
