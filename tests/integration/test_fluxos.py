import multiprocessing
from pathlib import Path

import pytest

import app
import music_library.downloader as yv
from music_library.library import filtrar_biblioteca


@pytest.mark.integration
def test_app_importa_sem_cookies_e_sem_rede(monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    assert callable(app.render_app)


@pytest.mark.integration
def test_biblioteca_vazia_e_estrutura_falsa(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DOWNLOADS_DIR", tmp_path / "downloads")
    assert app.biblioteca() == []
    faixa = app.DOWNLOADS_DIR / "Banda" / "Disco" / "01 - Música.mp3"
    faixa.parent.mkdir(parents=True)
    faixa.write_bytes(b"fake")
    assert app.biblioteca()[0]["Artista"] == "Banda"
    assert app.biblioteca()[0]["CD"] == "Disco"
    assert app.biblioteca()[0]["Status"] == "Sem catálogo"
    assert filtrar_biblioteca(app.biblioteca(), artista="Banda", cd="Disco") == app.biblioteca()


@pytest.mark.integration
def test_playlist_simulada_sucesso_e_parcial(monkeypatch, tmp_path):
    itens = [
        {"title": "Primeira", "url": "id1", "playlist_index": 1},
        {"title": "Segunda", "url": "id2", "playlist_index": 2},
    ]
    monkeypatch.setattr(yv, "obter_itens_playlist", lambda *_args: (itens, ""))

    def falso_item(_url, diretorio, _audio, titulo, indice, numerar):
        arquivo = Path(diretorio) / (f"{indice:02d} - {titulo}.mp3" if numerar else f"{titulo}.mp3")
        if titulo == "Segunda":
            return yv.ResultadoDownload(falhas=[f"{titulo}: indisponível"])
        arquivo.write_bytes(b"fake")
        return yv.ResultadoDownload(arquivos=[arquivo])

    monkeypatch.setattr(yv, "baixar_item", falso_item)
    resultado = yv.baixar_playlist("https://fake/?list=1", tmp_path, True, numerar_playlist=True)
    assert (tmp_path / "01 - Primeira.mp3").exists()
    assert yv.status_final(resultado) == "PARCIAL"
    assert resultado.falhas == ["Segunda: indisponível"]


@pytest.mark.integration
def test_segunda_tentativa_do_lock_e_bloqueada(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(app, "LOCK_FILE", app.LOGS_DIR / "download.lock")
    with app.lock_download() as primeira:
        assert primeira
        with app.lock_download() as segunda:
            assert not segunda
