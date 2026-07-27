#!/usr/bin/env python3
"""Baixador interativo de vídeos e playlists do YouTube com yt-dlp."""

import argparse
import importlib.metadata
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp

from .results import ResultadoDownload, status_final


RAIZ_PROJETO = Path(__file__).resolve().parent.parent
DIRETORIO_PADRAO = "./downloads"
EXTENSOES_TEMPORARIAS = {".part", ".ytdl", ".tmp"}
VERSAO_MINIMA_DENO = (2, 3, 0)
COOKIE_RUNTIME_PATH = Path(tempfile.gettempdir()) / "youtube-cookies-runtime.txt"


class ColoredFormatter(logging.Formatter):
    """Adiciona cores ao terminal, sem gravá-las no arquivo de log."""

    COLORS = {
        logging.DEBUG: "\033[90m",
        logging.INFO: "\033[92m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[95m",
    }
    RESET = "\033[0m"

    def format(self, record):
        message = super().format(record)
        return f"{self.COLORS.get(record.levelno, self.RESET)}{message}{self.RESET}"


class RegistradorYtDlp:
    """Encaminha diagnósticos do yt-dlp ao log e os preserva para o resumo."""

    def __init__(self):
        self.erros = []

    def debug(self, mensagem):
        logging.debug("yt-dlp: %s", mensagem)

    def warning(self, mensagem):
        logging.warning("yt-dlp: %s", mensagem)

    def error(self, mensagem):
        self.erros.append(str(mensagem))
        logging.error("yt-dlp: %s", mensagem)


def configurar_logs():
    """Cria o log fora do diretório de músicas, sempre na raiz do projeto."""
    diretorio_logs = RAIZ_PROJETO / "logs"
    diretorio_logs.mkdir(exist_ok=True)
    log_file = diretorio_logs / f"youtube_downloader_{datetime.now():%Y%m%d_%H%M%S}.log"

    formato = "%(asctime)s - %(levelname)s - %(message)s"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(formato))
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(ColoredFormatter(formato))
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler], force=True)
    return log_file


def verificar_diretorio(diretorio):
    try:
        Path(diretorio).mkdir(parents=True, exist_ok=True)
        return True
    except OSError as erro:
        logging.error("Erro ao criar/acessar diretório %s: %s", diretorio, erro)
        return False


def eh_playlist(url):
    return "list" in parse_qs(urlparse(url).query)


def arquivos_finais(diretorio):
    """Retorna arquivos concluídos; temporários do yt-dlp não contam como sucesso."""
    caminho = Path(diretorio)
    if not caminho.exists():
        return set()
    return {
        arquivo.resolve()
        for arquivo in caminho.rglob("*")
        if arquivo.is_file() and arquivo.suffix.lower() not in EXTENSOES_TEMPORARIAS
    }


def opcoes_desafio_javascript():
    """Opções locais: Deno no PATH, EJS instalado e sem componentes remotos."""
    opcoes = {
        "js_runtimes": {"deno": {}},
        "remote_components": [],
    }
    arquivo_cookies = os.environ.get("YTDLP_COOKIES_FILE")
    if arquivo_cookies:
        origem = Path(arquivo_cookies)
        if origem.is_file() and os.access(origem, os.R_OK):
            # yt-dlp pode atualizar o jar; nunca entregue o segredo montado como RO.
            shutil.copyfile(origem, COOKIE_RUNTIME_PATH)
            os.chmod(COOKIE_RUNTIME_PATH, 0o600)
            opcoes["cookiefile"] = str(COOKIE_RUNTIME_PATH)
    return opcoes


def classificar_erro(detalhe):
    texto = str(detalhe).lower()
    if "429" in texto or "too many requests" in texto:
        return "HTTP_429"
    if "cookie" in texto or "not a bot" in texto or "sign in to confirm" in texto or "authentication" in texto:
        return "AUTH"
    if "private" in texto:
        return "PRIVATE"
    if "format is not available" in texto or "no video formats" in texto:
        return "NO_FORMAT"
    if "unavailable" in texto or "not available" in texto:
        return "UNAVAILABLE"
    if "network" in texto or "timed out" in texto or "connection" in texto:
        return "NETWORK"
    return "UNKNOWN"


def mensagem_amigavel(categoria):
    return {
        "AUTH": "Sua sessão do YouTube expirou. Atualize o arquivo de cookies e tente novamente.",
        "HTTP_429": "O YouTube bloqueou tentativas temporariamente. Aguarde antes de tentar novamente.",
        "PRIVATE": "Esta fonte não está disponível. Escolha outra URL oficial.",
        "NO_FORMAT": "O YouTube não liberou áudio para esta URL. Escolha outra fonte oficial.",
        "UNAVAILABLE": "Esta fonte não está disponível. Escolha outra URL oficial.",
        "NETWORK": "Não foi possível acessar o YouTube agora. Tente novamente mais tarde.",
        "UNKNOWN": "Não foi possível processar esta fonte. Consulte o histórico para escolher outra URL.",
    }[categoria]


def validar_recursos_desafio(exigir_cookies=False):
    """Verifica pré-requisitos antes de qualquer acesso ao YouTube."""
    diagnosticos = []
    deno = shutil.which("deno")
    if not deno:
        diagnosticos.append("Deno não foi encontrado no PATH.")
    else:
        try:
            saida = subprocess.run([deno, "--version"], capture_output=True, check=True, text=True, timeout=10).stdout
            versao = tuple(int(parte) for parte in saida.splitlines()[0].split()[1].split(".")[:3])
            if versao < VERSAO_MINIMA_DENO:
                diagnosticos.append("Deno precisa estar na versão 2.3 ou superior.")
        except (OSError, subprocess.SubprocessError, IndexError, ValueError):
            diagnosticos.append("Não foi possível confirmar a versão do Deno.")
    try:
        importlib.metadata.version("yt-dlp-ejs")
    except importlib.metadata.PackageNotFoundError:
        diagnosticos.append("yt-dlp-ejs não está instalado.")
    if exigir_cookies:
        arquivo_cookies = os.environ.get("YTDLP_COOKIES_FILE")
        if not arquivo_cookies:
            diagnosticos.append("YTDLP_COOKIES_FILE não está configurada.")
        elif not Path(arquivo_cookies).is_file() or not os.access(arquivo_cookies, os.R_OK):
            diagnosticos.append("O arquivo de cookies configurado não está disponível para leitura.")
    return diagnosticos


def obter_opcoes(diretorio, somente_audio, numero_faixa=None, registrador=None):
    if numero_faixa is not None:
        # O item é baixado isoladamente para detectar sua falha; portanto, o
        # índice é fixado aqui em vez de depender de playlist_index do yt-dlp.
        nome_arquivo = f"{numero_faixa:02d} - %(title).200s.%(ext)s"
    else:
        nome_arquivo = "%(title).200s.%(ext)s"

    opcoes = {
        "outtmpl": str(Path(diretorio) / nome_arquivo),
        "format": "bestaudio/best" if somente_audio else "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "no_check_certificate": True,
        "quiet": False,
        "noprogress": False,
        # A playlist continua mesmo com itens indisponíveis. Cada retorno é validado abaixo.
        "ignoreerrors": True,
    }
    opcoes.update(opcoes_desafio_javascript())
    if registrador:
        opcoes["logger"] = registrador
    if somente_audio:
        opcoes["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    return opcoes


def baixar_item(url, diretorio, somente_audio, descricao, indice_playlist=None, numerar_playlist=False):
    """Baixa um item e só o considera sucesso se criou arquivo e retornou código zero."""
    resultado = ResultadoDownload()
    antes = arquivos_finais(diretorio)
    numero_faixa = indice_playlist if numerar_playlist and indice_playlist is not None else None
    registrador = RegistradorYtDlp()
    opcoes = obter_opcoes(diretorio, somente_audio, numero_faixa, registrador)
    opcoes["noplaylist"] = True

    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            codigo_retorno = ydl.download([url])
    except Exception as erro:  # yt-dlp pode lançar mesmo com ignoreerrors em alguns erros fatais.
        codigo_retorno = 1
        logging.error("Falha ao baixar '%s': %s", descricao, erro)

    criados = sorted(arquivos_finais(diretorio) - antes)
    resultado.arquivos.extend(criados)
    if codigo_retorno != 0 or not criados:
        motivo = f"código de retorno {codigo_retorno}" if codigo_retorno != 0 else "nenhum arquivo final criado"
        if registrador.erros:
            motivo = f"{motivo}; {registrador.erros[-1]}"
        categoria = classificar_erro(motivo)
        resultado.falhas.append(f"{descricao}: {mensagem_amigavel(categoria)}")
        logging.error("Falha técnica em '%s' (%s).", descricao, motivo)
    else:
        logging.info("Concluído: %s", descricao)
    return resultado


def baixar_item_da_playlist(url, diretorio, somente_audio, descricao, indice):
    """Baixa somente o índice solicitado de uma playlist já confirmada pela usuária."""
    resultado = ResultadoDownload()
    antes = arquivos_finais(diretorio)
    registrador = RegistradorYtDlp()
    opcoes = obter_opcoes(diretorio, somente_audio, indice, registrador)
    opcoes["playlist_items"] = str(indice)
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            codigo = ydl.download([url])
    except Exception as erro:
        codigo = 1
        logging.error("Falha técnica na playlist: %s", erro)
    criados = sorted(arquivos_finais(diretorio) - antes)
    resultado.arquivos.extend(criados)
    if codigo != 0 or not criados:
        motivo = f"código de retorno {codigo}" if codigo != 0 else "nenhum arquivo final criado"
        if registrador.erros:
            motivo = f"{motivo}; {registrador.erros[-1]}"
        categoria = classificar_erro(motivo)
        resultado.falhas.append(f"{descricao}: {mensagem_amigavel(categoria)}")
        logging.error("Falha técnica na faixa %s da playlist (%s).", indice, motivo)
    return resultado


def baixar_video(url, diretorio, somente_audio):
    logging.info("Preparando para baixar: %s", url)
    return baixar_item(url, diretorio, somente_audio, url)


def obter_itens_playlist(url_playlist, limite):
    """Obtém metadados da playlist para registrar falhas individualmente."""
    registrador = RegistradorYtDlp()
    opcoes = {
        "ignoreerrors": True,
        "skip_download": True,
        "extract_flat": "discard_in_playlist",
        "quiet": True,
        "logger": registrador,
    }
    opcoes.update(opcoes_desafio_javascript())
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url_playlist, download=False)
    except Exception as erro:
        logging.error("Não foi possível ler a playlist: %s", erro)
        return None, str(erro)

    if not info:
        return [], registrador.erros[-1] if registrador.erros else ""
    itens = list(info.get("entries") or [])
    return (itens[:limite] if limite else itens), ""


def baixar_playlist(url_playlist, diretorio, somente_audio, limite=None, numerar_playlist=True):
    logging.info("Preparando para baixar playlist diretamente em: %s", diretorio)
    resultado = ResultadoDownload()
    itens, diagnostico = obter_itens_playlist(url_playlist, limite)
    if itens is None:
        resultado.falhas.append(f"Playlist: não foi possível obter a lista de itens; {diagnostico}")
        return resultado
    if not itens:
        resultado.falhas.append(f"Playlist: nenhum item disponível para download; {diagnostico}")
        return resultado

    for posicao, item in enumerate(itens, start=1):
        if not item:
            resultado.falhas.append(f"Faixa {posicao}: item indisponível")
            logging.error("Faixa %s indisponível.", posicao)
            continue
        titulo = item.get("title") or f"Faixa {posicao}"
        url_item = item.get("webpage_url") or item.get("url")
        if not url_item:
            resultado.falhas.append(f"{titulo}: URL indisponível")
            logging.error("Faixa '%s' sem URL disponível.", titulo)
            continue
        if not url_item.startswith("http"):
            url_item = f"https://www.youtube.com/watch?v={url_item}"
        indice = item.get("playlist_index") or posicao
        resultado.adicionar(
            baixar_item(url_item, diretorio, somente_audio, titulo, indice, numerar_playlist)
        )
    return resultado


def executar_download(url, diretorio, somente_audio=True, limite=None, numerar_playlist=True, exigir_desafios_js=False):
    """API programática do downloader, reutilizável por interfaces locais."""
    diagnosticos = validar_recursos_desafio(exigir_cookies=exigir_desafios_js)
    if diagnosticos:
        return ResultadoDownload(falhas=diagnosticos)
    if not verificar_diretorio(diretorio):
        return ResultadoDownload(falhas=[f"Não foi possível acessar o diretório: {diretorio}"])
    if eh_playlist(url):
        return baixar_playlist(url, diretorio, somente_audio, limite, numerar_playlist)
    return baixar_video(url, diretorio, somente_audio)


def validar_url_sem_baixar(url):
    """Ação explícita: extrai metadados sem criar arquivo de música."""
    try:
        opcoes = opcoes_desafio_javascript() | {"skip_download": True, "simulate": True, "quiet": True}
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            ydl.extract_info(url, download=False)
        return "SUCESSO", "UNKNOWN", "Fonte validada sem download."
    except Exception as erro:
        categoria = classificar_erro(erro)
        logging.error("Falha técnica na validação de URL: %s", erro)
        return "FALHA", categoria, mensagem_amigavel(categoria)


def eh_bloqueio_temporario(resultado):
    """Identifica bloqueios que não devem ser repetidos automaticamente."""
    termos = ("http error 429", "too many requests", "not a bot", "sign in to confirm", "authentication", "autentica", "bloqueou tentativas temporariamente", "sessão do youtube expirou")
    texto = " ".join(resultado.falhas).lower()
    return any(termo in texto for termo in termos)


def exibir_resumo(resultado, inicio, log_file):
    status = status_final(resultado)
    logging.info("Resumo final: %d arquivo(s) baixado(s), %d falha(s).", len(resultado.arquivos), len(resultado.falhas))
    print("\n" + "=" * 50)
    print("RESUMO")
    print(f"Arquivos baixados: {len(resultado.arquivos)}")
    for arquivo in resultado.arquivos:
        print(f"  - {arquivo}")
    print(f"Falhas: {len(resultado.falhas)}")
    for falha in resultado.falhas:
        print(f"  - {falha}")
    print(f"Tempo decorrido: {time.time() - inicio:.1f}s")
    print(f"Logs detalhados: {log_file}")
    print(f"FINAL: {status}")
    print("=" * 50)
    return status


def ler_sim_nao(pergunta, padrao=True):
    resposta = input(pergunta).strip().lower()
    if not resposta:
        return padrao
    return resposta in {"s", "sim", "y", "yes"}


def main():  # pragma: no cover - fluxo interativo do CLI
    parser = argparse.ArgumentParser(description="Baixador interativo de vídeos e playlists do YouTube.")
    parser.parse_args()

    print("\n" + "=" * 50)
    print(" YouTube Playlist Downloader")
    print("=" * 50)
    diretorio_user = input(f"Informe o diretório onde salvar os arquivos (padrão: {DIRETORIO_PADRAO}): ").strip() or DIRETORIO_PADRAO
    log_file = configurar_logs()
    if not verificar_diretorio(diretorio_user):
        print("FINAL: FALHA")
        return 1

    logging.info("Diretório de downloads: %s", diretorio_user)
    logging.info("Arquivo de log: %s", log_file)
    url = input("Cole a URL do vídeo ou da playlist do YouTube: ").strip()
    if not url:
        logging.error("Nenhuma URL informada.")
        print("FINAL: FALHA")
        return 1
    somente_audio = ler_sim_nao("Baixar somente áudio? (s/n): ", padrao=False)
    limite_texto = input("Limite de vídeos da playlist, deixe em branco para todos: ").strip()
    try:
        limite = int(limite_texto) if limite_texto else None
    except ValueError:
        logging.warning("Limite inválido; serão processados todos os vídeos.")
        limite = None

    inicio = time.time()
    numerar = ler_sim_nao("Numerar faixas da playlist? (S/n): ", padrao=True) if eh_playlist(url) else False
    resultado = executar_download(url, diretorio_user, somente_audio, limite, numerar)
    return 0 if exibir_resumo(resultado, inicio, log_file) == "SUCESSO" else 1


if __name__ == "__main__":
    sys.exit(main())
