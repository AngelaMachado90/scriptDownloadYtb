"""Interface local da Biblioteca do Ariel."""

import fcntl
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from music_library.downloader import (
    RAIZ_PROJETO,
    configurar_logs,
    eh_bloqueio_temporario,
    executar_download,
    status_final,
)


DOWNLOADS_DIR = (RAIZ_PROJETO / "downloads").resolve()
LOGS_DIR = RAIZ_PROJETO / "logs"
LOCK_FILE = LOGS_DIR / "download.lock"
NOME_NOVO = "Criar novo"


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
    registros = []
    for artista in artistas_existentes():
        albuns = albuns_existentes(artista)
        if not albuns:
            quantidade = sum(1 for arquivo in (DOWNLOADS_DIR / artista).glob("*.mp3") if arquivo.is_file())
            registros.append({"Artista": artista, "Álbum": "—", "MP3s": quantidade})
        for album in albuns:
            quantidade = sum(1 for arquivo in (DOWNLOADS_DIR / artista / album).rglob("*.mp3") if arquivo.is_file())
            registros.append({"Artista": artista, "Álbum": album, "MP3s": quantidade})
    return registros


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
        artistas = artistas_existentes()
        artista_bruto = escolher_nome("Artista", artistas, "artista")
        try:
            artista_validado = nome_seguro(artista_bruto, "o artista") if artista_bruto else ""
        except ValueError as erro:
            artista_validado = ""
            st.error(str(erro))
        albuns = albuns_existentes(artista_validado) if artista_validado else []
        album_bruto = escolher_nome("Álbum", albuns, "album")
        try:
            album_validado = nome_seguro(album_bruto, "o álbum") if album_bruto else ""
            destino = diretorio_do_album(artista_validado, album_validado) if artista_validado and album_validado else None
        except ValueError as erro:
            album_validado, destino = "", None
            st.error(str(erro))
        if destino:
            st.code(str(destino), language=None)
        url = st.text_input("URL do vídeo ou playlist", placeholder="https://www.youtube.com/watch?v=...")
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
            st.dataframe(registros, hide_index=True, use_container_width=True)
            st.caption(f"Total de MP3s: {sum(registro['MP3s'] for registro in registros)}")
        else:
            st.info("Nenhum artista ou álbum encontrado ainda.")
    st.divider()
    st.subheader("Logs")
    logs = sorted(LOGS_DIR.glob("*.log"), key=lambda arquivo: arquivo.stat().st_mtime, reverse=True) if LOGS_DIR.exists() else []
    if logs:
        selecionado = st.selectbox("Arquivo de log", logs, format_func=lambda arquivo: arquivo.name)
        st.code(ler_log(selecionado), language="text")
    else:
        st.caption("Os logs aparecerão aqui após o primeiro download.")


if __name__ == "__main__":
    render_app()
