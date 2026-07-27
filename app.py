"""Interface local da Biblioteca do Ariel."""

import fcntl
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from music_library.downloader import (
    RAIZ_PROJETO,
    baixar_item,
    baixar_item_da_playlist,
    configurar_logs,
    eh_bloqueio_temporario,
    executar_download,
    status_final,
    validar_url_sem_baixar,
)
from music_library.library import catalogo_do_album, filtrar_biblioteca, listar_biblioteca
from music_library.history import HistoryStore
from music_library.official_artists import artista_oficial, busca_oficial, url_pertence_ao_canal
from music_library.track_sources import best_source, sources_for_track
from music_library.album_sources import albums_for_artist as albums_catalogados, artists_with_album_sources, best_album_source
from music_library.missing_downloads import acao_por_cd, executar_plano, planejar_faixas_faltantes


DOWNLOADS_DIR = (RAIZ_PROJETO / "downloads").resolve()
LOGS_DIR = RAIZ_PROJETO / "logs"
LOCK_FILE = LOGS_DIR / "download.lock"
NOME_NOVO = "Criar novo"

def dados_visuais_status(status):
    """Retorna o ícone Bootstrap e o texto correspondente ao status."""
    configuracoes = {
        "Completo": {
            "icone": (
                "https://api.iconify.design/bi/check-circle-fill.svg"
                "?color=%23198754"
            ),
            "texto": "Completo",
        },
        "Incompleto": {
            "icone": (
                "https://api.iconify.design/bi/exclamation-circle-fill.svg"
                "?color=%23ffc107"
            ),
            "texto": "Incompleto",
        },
        "Sem faixas": {
            "icone": (
                "https://api.iconify.design/bi/dash-circle-fill.svg"
                "?color=%236c757d"
            ),
            "texto": "Sem faixas",
        },
    }

    return configuracoes.get(
        status,
        {
            "icone": (
                "https://api.iconify.design/bi/info-circle-fill.svg"
                "?color=%230dcaf0"
            ),
            "texto": str(status),
        },
    )


def preparar_tabela_biblioteca(registros):
    """Prepara os registros exibidos no dataframe da biblioteca."""
    tabela = []

    for registro in registros:
        status = dados_visuais_status(registro["Status"])

        tabela.append(
            {
                "Ícone": status["icone"],
                "Artista": registro["Artista"],
                "CD": registro["CD"],
                "Progresso": registro["Progresso"],
                "Status": status["texto"],
            }
        )

    return tabela


@contextmanager
def lock_download():
    """Impede dois processos da interface de iniciarem downloads ao mesmo tempo."""
    LOGS_DIR.mkdir(exist_ok=True)
    with LOCK_FILE.open("a+", encoding="utf-8") as arquivo_lock:
        try:
            fcntl.flock(arquivo_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(arquivo_lock.fileno(), fcntl.LOCK_UN)


def nome_seguro(valor, campo):
    valor = unicodedata.normalize("NFC", valor).strip()
    if not valor:
        raise ValueError(f"Informe {campo}.")
    if len(valor) > 100 or valor in {".", ".."} or "\x00" in valor:
        raise ValueError(f"{campo} inválido.")
    if any(separador in valor for separador in ("/", "\\")) or Path(valor).name != valor:
        raise ValueError(f"{campo} não pode conter caminhos ou separadores.")
    return valor


def diretorio_do_album(artista, album):
    destino = (DOWNLOADS_DIR / artista / album).resolve()
    try:
        destino.relative_to(DOWNLOADS_DIR)
    except ValueError as erro:
        raise ValueError("Diretório de destino inválido.") from erro
    return destino


def artistas_existentes():
    if not DOWNLOADS_DIR.exists():
        return []
    return sorted(p.name for p in DOWNLOADS_DIR.iterdir() if p.is_dir())


def albuns_existentes(artista):
    raiz_artista = DOWNLOADS_DIR / artista
    if not raiz_artista.is_dir():
        return []
    return sorted(p.name for p in raiz_artista.iterdir() if p.is_dir())


def biblioteca():
    return listar_biblioteca(DOWNLOADS_DIR)


def url_youtube_valida(url):
    partes = urlparse(url.strip())
    host = (partes.hostname or "").lower()
    return partes.scheme in {"http", "https"} and (host == "youtu.be" or host.endswith(".youtube.com") or host == "youtube.com")


def ler_log(caminho):
    try:
        with caminho.open("r", encoding="utf-8", errors="replace") as arquivo:
            return "".join(arquivo.readlines()[-300:])
    except OSError as erro:
        return f"Não foi possível ler o log: {erro}"


def escolher_nome(rotulo, existentes, chave):
    escolha = st.selectbox(rotulo, [NOME_NOVO, *existentes], key=f"{chave}_escolha")
    if escolha == NOME_NOVO:
        return st.text_input(f"Novo {rotulo.lower()}", key=f"{chave}_novo")
    return escolha


def render_app():  # pragma: no cover - renderizado pelo Streamlit em execução
    """Renderiza a interface; mantida fora do import para testes isolados."""
    st.set_page_config(page_title="Biblioteca do Ariel", page_icon="🎵", layout="wide")
    st.title("🎵 Biblioteca do Ariel")
    st.caption("Organize músicas para pendrive e som automotivo, sempre dentro da biblioteca local.")
    with st.sidebar:
        st.subheader("Status")
        st.info(st.session_state.get("status_download", "Aguardando download."))
        st.caption(f"Biblioteca: {DOWNLOADS_DIR}")
    coluna_formulario, coluna_biblioteca = st.columns([1, 1])
    with coluna_formulario:
        st.subheader("Novo download")
        artistas = sorted(set(artistas_existentes()) | set(artists_with_album_sources()))
        artista_bruto = escolher_nome("Artista", artistas, "artista")
        try:
            artista_validado = nome_seguro(artista_bruto, "o artista") if artista_bruto else ""
        except ValueError as erro:
            artista_validado = ""
            st.error(str(erro))
        albuns = sorted(set(albuns_existentes(artista_validado)) | set(albums_catalogados(artista_validado))) if artista_validado else []
        album_bruto = escolher_nome("Álbum", albuns, "album")
        try:
            album_validado = nome_seguro(album_bruto, "o álbum") if album_bruto else ""
            destino = diretorio_do_album(artista_validado, album_validado) if artista_validado and album_validado else None
        except ValueError as erro:
            album_validado, destino = "", None
            st.error(str(erro))
        if destino:
            st.code(str(destino), language=None)
        fonte_album = best_album_source(artista_validado, album_validado) if artista_validado and album_validado else None
        if fonte_album:
            st.success("Fonte: playlist de álbum")
        url = st.text_input("URL do vídeo ou playlist", value=fonte_album["url"] if fonte_album else "", placeholder="https://www.youtube.com/watch?v=...")
        somente_audio = st.checkbox("Somente áudio", value=True)
        numerar = st.checkbox("Numerar faixas para o carro", value=True)
        iniciar = st.button("Iniciar download", type="primary", use_container_width=True)
        if iniciar:
            if not destino:
                st.error("Escolha ou informe Artista e Álbum válidos.")
            elif not url_youtube_valida(url):
                st.error("Informe uma URL válida de YouTube ou youtu.be.")
            else:
                with lock_download() as adquirido:
                    if not adquirido:
                        st.warning("Já existe um download em andamento nesta biblioteca. Aguarde a conclusão.")
                    else:
                        destino.mkdir(parents=True, exist_ok=True)
                        log_file = configurar_logs()
                        st.session_state.status_download = "Baixando…"
                        with st.spinner("Baixando e organizando as faixas…"):
                            resultado = executar_download(url.strip(), destino, somente_audio, numerar_playlist=numerar, exigir_desafios_js=True)
                        final = status_final(resultado)
                        st.session_state.status_download = f"{final}: {len(resultado.arquivos)} arquivo(s), {len(resultado.falhas)} falha(s)."
                        st.session_state.ultimo_resultado = resultado
                        st.session_state.ultimo_log = str(log_file)
                        if eh_bloqueio_temporario(resultado):
                            st.error("Bloqueio temporário do YouTube (429, verificação anti-bot ou autenticação). Nenhuma nova tentativa foi feita automaticamente.")
                        elif final == "SUCESSO":
                            st.success("Download concluído com sucesso.")
                        elif final == "PARCIAL":
                            st.warning("Download parcial: consulte as falhas abaixo.")
                        else:
                            st.error("Download falhou: nenhum arquivo foi criado.")
        resultado = st.session_state.get("ultimo_resultado")
        if resultado:
            st.subheader("Resumo final")
            st.write(f"**Arquivos baixados:** {len(resultado.arquivos)}")
            st.write(f"**Falhas:** {len(resultado.falhas)}")
            if resultado.arquivos:
                st.code("\n".join(str(arquivo) for arquivo in resultado.arquivos), language=None)
            if resultado.falhas:
                st.error("\n".join(f"• {falha}" for falha in resultado.falhas))
    with coluna_biblioteca:
        st.subheader("Minha biblioteca")
        registros = biblioteca()
        if registros:
            artistas_filtro = ["Todos os artistas", *sorted({registro["Artista"] for registro in registros})]
            artista_filtro = st.selectbox("Filtrar por artista", artistas_filtro) or "Todos os artistas"
            cds_filtro = ["Todos os CDs", *sorted({registro["CD"] for registro in registros if artista_filtro == "Todos os artistas" or registro["Artista"] == artista_filtro})]
            cd_filtro = st.selectbox("Filtrar por CD", cds_filtro) or "Todos os CDs"
            exibidos = filtrar_biblioteca(registros, artista_filtro, cd_filtro)
            st.dataframe([{chave: registro[chave] for chave in ("Artista", "CD", "Progresso", "Status")} for registro in exibidos], hide_index=True, use_container_width=True)
            for registro in exibidos:
                atual, total = (map(int, registro["Progresso"].split(" / ")) if registro["Progresso"] != "—" else (0, 0))
                if total:
                    st.progress(atual / total, text=f'{registro["Artista"]} — {registro["CD"]}: {registro["Progresso"]}')
                catalogo = catalogo_do_album(registro["Artista"], registro["CD"])
                fonte_album_linha = best_album_source(registro["Artista"], registro["CD"])
                tem_fonte_individual = bool(catalogo and any(sources_for_track(registro["Artista"], registro["CD"], faixa) for faixa in catalogo["faixas"]))
                tem_fonte = bool(fonte_album_linha or tem_fonte_individual)
                acao = acao_por_cd(registro, bool(catalogo), bool(fonte_album_linha) if registro["Status"] == "Sem faixas" else tem_fonte)
                if acao["tipo"] == "completo":
                    st.button(acao["texto"], key=f"completo-{registro['Artista']}-{registro['CD']}", disabled=True)
                elif acao["tipo"] == "sem_faltantes":
                    st.button(acao["texto"], key=f"sem-faltantes-{registro['Artista']}-{registro['CD']}", disabled=True)
                    st.caption("Há arquivos duplicados ou extras; nenhum download será iniciado.")
                elif acao["tipo"] == "sem_fonte":
                    st.button(acao["texto"], key=f"sem-fonte-{registro['Artista']}-{registro['CD']}", disabled=True)
                    st.caption("Cadastre a playlist do álbum ou uma fonte por faixa antes de baixar.")
                elif acao["tipo"] == "album":
                    if not fonte_album_linha:
                        st.button(acao["texto"], key=f"baixar-album-{registro['Artista']}-{registro['CD']}", disabled=True)
                        st.caption("Fonte de álbum não encontrada.")
                    elif st.button(acao["texto"], key=f"baixar-album-{registro['Artista']}-{registro['CD']}"):
                        destino_lote = diretorio_do_album(registro["Artista"], registro["CD"])
                        with lock_download() as adquirido:
                            if not adquirido:
                                st.warning("Já existe um download em andamento nesta biblioteca. Aguarde a conclusão.")
                            else:
                                destino_lote.mkdir(parents=True, exist_ok=True)
                                log_file = configurar_logs()
                                with st.spinner("Baixando o CD…"):
                                    resultado_album = executar_download(fonte_album_linha["url"], destino_lote, True, numerar_playlist=True, exigir_desafios_js=True)
                                st.session_state.ultimo_log = str(log_file)
                                if resultado_album.arquivos:
                                    st.success(f"CD: {len(resultado_album.arquivos)} música(s) baixada(s).")
                                if resultado_album.falhas:
                                    st.warning("Algumas músicas não puderam ser baixadas.")
                                st.rerun()
                elif acao["tipo"] == "faltantes":
                    historico_lote = HistoryStore(RAIZ_PROJETO / "data" / "library_history.sqlite")
                    destino_lote = diretorio_do_album(registro["Artista"], registro["CD"])
                    plano = planejar_faixas_faltantes(registro["Artista"], registro["CD"], destino_lote, historico_lote)
                    if st.button(f"Baixar músicas faltantes ({len(plano)})", key=f"baixar-faltantes-{registro['Artista']}-{registro['CD']}"):
                        if not plano:
                            st.info("As faixas já existem na biblioteca ou não há uma fonte disponível no momento.")
                        else:
                            st.info("Baixando, uma por vez: " + ", ".join(item["track"] for item in plano))

                            def baixar_planejada(item, destino):
                                if item["kind"] == "playlist_item":
                                    return baixar_item_da_playlist(item["url"], destino, True, item["track"], item["index"])
                                return baixar_item(item["url"], destino, True, item["track"], item["index"], numerar_playlist=True)

                            with lock_download() as adquirido:
                                if not adquirido:
                                    st.warning("Já existe um download em andamento nesta biblioteca. Aguarde a conclusão.")
                                else:
                                    destino_lote.mkdir(parents=True, exist_ok=True)
                                    log_file = configurar_logs()
                                    st.session_state.status_download = "Baixando músicas faltantes…"
                                    with st.spinner("Baixando somente as faixas faltantes…"):
                                        resultado_lote = executar_plano(plano, destino_lote, baixar_planejada, historico_lote)
                                    st.session_state.ultimo_log = str(log_file)
                                    if resultado_lote["baixadas"]:
                                        st.success("Músicas baixadas: " + ", ".join(resultado_lote["baixadas"]))
                                    if resultado_lote["faltando"]:
                                        st.warning("Continuam faltando: " + ", ".join(resultado_lote["faltando"]))
                                    if resultado_lote["alternativas"]:
                                        st.info("Há outra fonte cadastrada para: " + ", ".join(resultado_lote["alternativas"]) + ". Escolha-a no detalhe da faixa.")
                                    if not resultado_lote["baixadas"] and not resultado_lote["faltando"]:
                                        st.info("As faixas já existem na biblioteca.")
                                    st.rerun()
                    historico_lote.close()
                if cd_filtro == registro["CD"] and registro["Status"] == "Incompleto" and registro["faltantes"]:
                    st.warning("Faixas faltantes: " + ", ".join(registro["faltantes"]))
                    historico = HistoryStore(RAIZ_PROJETO / "data" / "library_history.sqlite")
                    proxima = st.session_state.get(f"proxima-{registro['CD']}", registro["faltantes"][0])
                    if proxima not in registro["faltantes"]:
                        proxima = registro["faltantes"][0]
                    fonte_recomendada = best_source(registro["Artista"], registro["CD"], proxima, historico)
                    st.info(f"Próxima faixa: {proxima}")
                    if fonte_recomendada:
                        st.success("Fonte oficial")
                    else:
                        st.caption("Nenhuma fonte disponível agora; verifique bloqueios ou associe uma URL manualmente.")
                    if st.button("Concluir CD", key=f"concluir-{registro['CD']}"):
                        st.info("Cadastre ou escolha uma fonte para testar uma faixa por vez.")
                    for faixa in registro["faltantes"]:
                        fontes = historico.sources(registro["Artista"], registro["CD"], faixa)
                        with st.expander(f"{faixa} — {len(fontes)} fonte(s) disponível(is)"):
                            oficial = artista_oficial(registro["Artista"])
                            if oficial:
                                st.success("Canal oficial cadastrado")
                                st.caption(oficial["youtube_channel"])
                            recomendada = fonte_recomendada["url"] if faixa == proxima and fonte_recomendada else ""
                            url_manual = st.text_input("Adicionar URL", value=recomendada, key=f"url-{registro['CD']}-{faixa}")
                            if st.button("Adicionar URL", key=f"adicionar-{registro['CD']}-{faixa}") and url_manual:
                                historico.add_candidate(registro["Artista"], registro["CD"], faixa, url_manual)
                                st.rerun()
                            st.link_button("Buscar fonte oficial", busca_oficial(registro["Artista"], faixa))
                            for fonte in fontes:
                                if fonte["next_retry_at"]:
                                    st.caption(f"Não tentar novamente antes de {fonte['next_retry_at'][:10].split('-')[2]}/{fonte['next_retry_at'][:10].split('-')[1]}/{fonte['next_retry_at'][:10].split('-')[0]} — {fonte['error_category']}: {fonte['message']}")
                                if st.button("Testar URL sem baixar", key=f"testar-{fonte['id']}"):
                                    resultado_teste, categoria, mensagem = validar_url_sem_baixar(fonte["url"])
                                    historico.record_attempt(fonte["id"], resultado_teste, categoria, mensagem)
                                    if resultado_teste == "SUCESSO":
                                        st.success(mensagem)
                                    else:
                                        st.error(mensagem)
                                    st.rerun()
                                if st.button("Baixar esta faixa", key=f"baixar-{fonte['id']}"):
                                    resultado_download = executar_download(fonte["url"], DOWNLOADS_DIR / registro["Artista"] / registro["CD"], True, exigir_desafios_js=True)
                                    if resultado_download.falhas:
                                        mensagem = resultado_download.falhas[-1]
                                        categoria = "UNKNOWN"
                                        historico.record_attempt(fonte["id"], "FALHA", categoria, mensagem)
                                        st.error(mensagem)
                                    else:
                                        historico.record_attempt(fonte["id"], "SUCESSO", "UNKNOWN", "Download concluído.")
                                        historico.record_download(registro["Artista"], registro["CD"], faixa, fonte["url"])
                                        st.success("Download concluído.")
                                    st.rerun()
                                if oficial and url_pertence_ao_canal(fonte["url"], registro["Artista"]) and st.button("Marcar como verificada oficialmente", key=f"oficial-{fonte['id']}"):
                                    historico.mark_official(fonte["id"])
                                    st.rerun()
                            if fontes and st.button("Tentar próxima fonte disponível", key=f"proxima-{registro['CD']}-{faixa}"):
                                st.warning("Confirme a URL desejada: apenas uma fonte pode ser testada por vez.")
                    if st.button("Próxima faixa faltante", key=f"avancar-{registro['CD']}"):
                        st.session_state[f"proxima-{registro['CD']}"] = registro["faltantes"][1] if len(registro["faltantes"]) > 1 else proxima
                    historico.close()
        else:
            st.info("Nenhum artista ou álbum encontrado ainda.")
    st.divider()
    with st.expander("Histórico de falhas"):
        historico = HistoryStore(RAIZ_PROJETO / "data" / "library_history.sqlite")
        registros_historico = [dict(linha) for linha in historico.history()]
        if registros_historico:
            st.dataframe(registros_historico, hide_index=True, use_container_width=True)
        else:
            st.caption("Nenhuma tentativa registrada.")
        historico.close()
    st.subheader("Logs")
    logs = sorted(LOGS_DIR.glob("*.log"), key=lambda arquivo: arquivo.stat().st_mtime, reverse=True) if LOGS_DIR.exists() else []
    if logs:
        selecionado = st.selectbox("Arquivo de log", logs, format_func=lambda arquivo: arquivo.name)
        st.code(ler_log(selecionado), language="text")
    else:
        st.caption("Os logs aparecerão aqui após o primeiro download.")


if __name__ == "__main__":
    render_app()
