import os
import sys
import time
import logging
from urllib.parse import urlparse, parse_qs
import yt_dlp
#correcao http
# Caminho padrão de downloads
DIRETORIO_PADRAO = "/mnt/server/downloads"

# Classe para colorir logs no terminal
class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[90m",
        logging.INFO: "\033[92m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[95m",
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{log_color}{message}{self.RESET}"

def configurar_logs(log_file):
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    color_formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s')

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(log_formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(color_formatter)

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, stream_handler])

def verificar_diretorio(diretorio):
    try:
        os.makedirs(diretorio, exist_ok=True)
        logging.info(f"Diretório de downloads: {diretorio}")
        return True
    except Exception as e:
        logging.error(f"Erro ao acessar diretório: {e}", exc_info=True)
        return False

def eh_playlist(url):
    query = parse_qs(urlparse(url).query)
    return 'list' in query

def obter_opcoes(diretorio, somente_audio):
    opcoes = {
        'outtmpl': os.path.join(diretorio, '%(title).200s.%(ext)s'),
        'format': 'bestaudio/best' if somente_audio else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'no_check_certificate': True,  # Ignora problemas de certificado SSL
        'quiet': False,
        'noprogress': False,
    }

    if somente_audio:
        opcoes['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    return opcoes

def baixar_video(url, diretorio, somente_audio):
    try:
        logging.debug(f"Preparando para baixar: {url}")
        start_time = time.time()

        ydl_opts = obter_opcoes(diretorio, somente_audio)
        ydl_opts['noplaylist'] = True

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        logging.info(f"Download concluído em {time.time()-start_time:.1f}s")
        return True

    except Exception as e:
        logging.error(f"Falha ao baixar {url}: {str(e)}", exc_info=True)
        return False

def baixar_playlist(url_playlist, diretorio, somente_audio, limite=None):
    try:
        if not verificar_diretorio(diretorio):
            return False

        ydl_opts = obter_opcoes(diretorio, somente_audio)
        ydl_opts['outtmpl'] = os.path.join(diretorio, '%(playlist_title)s/%(title).200s.%(ext)s')

        if limite:
            ydl_opts['playlistend'] = limite

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_playlist])

        logging.info("Download da playlist finalizado.")
        return True

    except Exception as e:
        logging.error(f"Erro ao processar playlist: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    print("\n" + "="*50)
    print(" YouTube Playlist Downloader - Versão Corrigida ")
    print("   Desenvolvido por Angela Machado - 2025-07-02")
    print("="*50)

    # Solicita diretório de destino ou usa padrão
    diretorio_user = input(f"Informe o diretório onde salvar os arquivos (padrão: {DIRETORIO_PADRAO}): ").strip()
    if not diretorio_user:
        diretorio_user = DIRETORIO_PADRAO

    LOG_FILE = os.path.join(diretorio_user, "youtube_downloader.log")
    configurar_logs(LOG_FILE)

    if not verificar_diretorio(diretorio_user):
        print("Erro ao acessar o diretório de downloads. Verifique permissões.")
        sys.exit(1)

    url = input("Cole a URL do vídeo ou da playlist do YouTube: ").strip()
    somente_audio = input("Baixar somente áudio? (s/n): ").lower() == 's'
    limite = input("Limite de vídeos (deixe em branco para todos): ").strip()

    try:
        limite = int(limite) if limite else None
    except ValueError:
        logging.warning("Valor inválido para limite. Baixando todos os vídeos.")
        limite = None

    logging.info("\nIniciando processo de download...")
    start_time = time.time()

    if eh_playlist(url):
        sucesso = baixar_playlist(url, diretorio_user, somente_audio, limite)
    else:
        sucesso = baixar_video(url, diretorio_user, somente_audio)

    if sucesso:
        logging.info(f"\nProcesso concluído com sucesso em {time.time()-start_time:.1f} segundos!")
    else:
        logging.error("\nOcorreram erros durante o download!")

    print(f"\nLogs detalhados salvos em: {LOG_FILE}")
    print("="*50)
    print("Obrigado por usar o YouTube Playlist Downloader!")
    print("="*50)
    print("\n")
