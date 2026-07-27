import os

from music_library import downloader
from music_library.library import catalogo_do_album


def test_cookie_ro_e_copia_runtime_atualizada(monkeypatch, tmp_path):
    origem = tmp_path / "cookies-ro.txt"
    runtime = tmp_path / "runtime.txt"
    origem.write_text("primeira", encoding="utf-8")
    origem.chmod(0o400)
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(origem))
    monkeypatch.setattr(downloader, "COOKIE_RUNTIME_PATH", runtime)
    assert downloader.opcoes_desafio_javascript()["cookiefile"] == str(runtime)
    assert runtime.read_text(encoding="utf-8") == "primeira"
    assert oct(runtime.stat().st_mode & 0o777) == "0o600"
    origem.chmod(0o600)
    origem.write_text("segunda", encoding="utf-8")
    downloader.opcoes_desafio_javascript()
    assert runtime.read_text(encoding="utf-8") == "segunda"


def test_mensagem_cookie_expirado_e_divisive_com_dez_faixas():
    assert downloader.mensagem_amigavel(downloader.classificar_erro("cookies are no longer valid")) == "Sua sessão do YouTube expirou. Atualize o arquivo de cookies e tente novamente."
    assert len(catalogo_do_album("Disturbed", "2022 - Divisive")["faixas"]) == 10
