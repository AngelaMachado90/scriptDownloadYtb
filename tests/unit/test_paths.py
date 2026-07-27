import pytest

import app


@pytest.mark.unit
@pytest.mark.parametrize("valor", ["../fora", "a/b", "a\\b", ".", "..", "", "\x00nome"])
def test_nome_seguro_bloqueia_path_traversal(valor):
    with pytest.raises(ValueError):
        app.nome_seguro(valor, "o artista")


@pytest.mark.unit
def test_nome_e_diretorio_somente_dentro_de_downloads(monkeypatch, tmp_path):
    downloads = tmp_path / "downloads"
    monkeypatch.setattr(app, "DOWNLOADS_DIR", downloads)
    artista = app.nome_seguro(" Artista ", "o artista")
    album = app.nome_seguro("Álbum", "o álbum")
    destino = app.diretorio_do_album(artista, album)
    destino.mkdir(parents=True)
    assert destino == downloads / "Artista" / "Álbum"
    with pytest.raises(ValueError):
        app.diretorio_do_album("..", "fora")


@pytest.mark.unit
def test_helpers_da_biblioteca_e_url(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DOWNLOADS_DIR", tmp_path / "downloads")
    faixa = app.DOWNLOADS_DIR / "Artista" / "Album" / "faixa.mp3"
    faixa.parent.mkdir(parents=True)
    faixa.write_bytes(b"fake")
    assert app.artistas_existentes() == ["Artista"]
    assert app.albuns_existentes("Artista") == ["Album"]
    assert app.url_youtube_valida("https://youtu.be/id")
    assert not app.url_youtube_valida("https://example.org/id")
    log = tmp_path / "log.txt"
    log.write_text("linha\n", encoding="utf-8")
    assert app.ler_log(log) == "linha\n"
    assert "Não foi possível ler" in app.ler_log(tmp_path / "ausente.log")
