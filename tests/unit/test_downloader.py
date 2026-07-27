import logging
from pathlib import Path

import pytest

import music_library.downloader as yv


class YdlFalso:
    codigo = 0
    criar = True
    erro = None

    def __init__(self, opcoes):
        self.opcoes = opcoes

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def download(self, _urls):
        if self.erro:
            self.opcoes["logger"].error(self.erro)
        if self.criar:
            destino = Path(self.opcoes["outtmpl"]).parent / "arquivo-falso.mp3"
            destino.write_bytes(b"fake")
        return self.codigo


@pytest.mark.unit
def test_url_video_e_playlist():
    assert not yv.eh_playlist("https://youtu.be/abc")
    assert yv.eh_playlist("https://www.youtube.com/watch?v=abc&list=PL123")


@pytest.mark.unit
def test_numeracao_playlist_e_status():
    assert yv.arquivos_finais("/diretorio-inexistente") == set()
    assert Path(yv.obter_opcoes("/tmp", True, 1)["outtmpl"]).name == "01 - %(title).200s.%(ext)s"
    assert yv.status_final(yv.ResultadoDownload([Path("a.mp3")])) == "SUCESSO"
    assert yv.status_final(yv.ResultadoDownload([Path("a.mp3")], ["erro"])) == "PARCIAL"
    assert yv.status_final(yv.ResultadoDownload(falhas=["erro"])) == "FALHA"


@pytest.mark.unit
def test_bloqueio_de_cookie_ou_429_nao_configura_retativas():
    registrador = yv.RegistradorYtDlp()
    registrador.warning("The provided YouTube account cookies are no longer valid")
    assert registrador.bloqueio == "AUTH"
    opcoes = yv.obter_opcoes("/tmp", True, registrador=registrador)
    assert opcoes["retries"] == 0
    assert opcoes["extractor_retries"] == 0
    assert opcoes["fragment_retries"] == 0


@pytest.mark.unit
def test_arquivo_criado_nao_anula_retorno_de_erro(monkeypatch, tmp_path):
    monkeypatch.setattr(yv.yt_dlp, "YoutubeDL", YdlFalso)
    monkeypatch.setattr(yv, "opcoes_desafio_javascript", lambda: {})
    YdlFalso.codigo, YdlFalso.criar, YdlFalso.erro = 1, True, "HTTP Error 429"
    resultado = yv.baixar_item("fake://video", tmp_path, True, "Faixa")
    assert len(resultado.arquivos) == 1
    assert resultado.falhas and yv.status_final(resultado) == "PARCIAL"
    assert yv.eh_bloqueio_temporario(resultado)


@pytest.mark.unit
@pytest.mark.parametrize("mensagem,bloqueio", [
    ("Sign in to confirm you're not a bot", True),
    ("Private video", False),
    ("Requested format is not available", False),
])
def test_falhas_do_ytdlp_sao_registradas_sem_sucesso(monkeypatch, tmp_path, mensagem, bloqueio):
    monkeypatch.setattr(yv.yt_dlp, "YoutubeDL", YdlFalso)
    monkeypatch.setattr(yv, "opcoes_desafio_javascript", lambda: {})
    YdlFalso.codigo, YdlFalso.criar, YdlFalso.erro = 1, False, mensagem
    resultado = yv.baixar_item("fake://video", tmp_path, True, "Faixa")
    assert not resultado.arquivos and resultado.falhas
    assert yv.status_final(resultado) == "FALHA"
    assert yv.eh_bloqueio_temporario(resultado) is bloqueio


@pytest.mark.unit
def test_logs_ficam_fora_da_biblioteca_e_cookie_nao_vaza(monkeypatch, tmp_path):
    raiz = tmp_path / "projeto"
    musica = raiz / "downloads" / "Artista" / "Album"
    musica.mkdir(parents=True)
    secreto = tmp_path / "cookies.txt"
    secreto.write_text("conteudo-sensivel", encoding="utf-8")
    runtime = tmp_path / "cookies-runtime.txt"
    monkeypatch.setattr(yv, "RAIZ_PROJETO", raiz)
    monkeypatch.setattr(yv, "COOKIE_RUNTIME_PATH", runtime)
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(secreto))
    opcoes = yv.opcoes_desafio_javascript()
    log_file = yv.configurar_logs()
    logging.info("evento de teste")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert opcoes["cookiefile"] == str(runtime)
    assert log_file.parent == raiz / "logs"
    assert not list(musica.glob("*.log"))
    assert str(secreto) not in log_file.read_text(encoding="utf-8")


@pytest.mark.unit
def test_recursos_js_e_execucao_sem_acesso_externo(monkeypatch, tmp_path):
    monkeypatch.setattr(yv.shutil, "which", lambda _nome: "/fake/deno")
    monkeypatch.setattr(yv.subprocess, "run", lambda *_a, **_k: type("R", (), {"stdout": "deno 2.4.0\n"})())
    monkeypatch.setattr(yv.importlib.metadata, "version", lambda _nome: "0.8.0")
    cookie = tmp_path / "cookie.txt"
    cookie.write_text("fake", encoding="utf-8")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(cookie))
    assert yv.validar_recursos_desafio(exigir_cookies=True) == []
    monkeypatch.setattr(yv, "baixar_video", lambda *_a: yv.ResultadoDownload(falhas=["simulado"]))
    assert yv.executar_download("https://youtu.be/id", tmp_path, exigir_desafios_js=True).falhas == ["simulado"]


@pytest.mark.unit
def test_playlist_sem_itens_e_resumo(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(yv, "obter_itens_playlist", lambda *_a: ([], "indisponível"))
    resultado = yv.baixar_playlist("https://fake/?list=1", tmp_path, True)
    assert yv.status_final(resultado) == "FALHA"
    assert yv.exibir_resumo(resultado, 0, tmp_path / "log.txt") == "FALHA"
    assert "FINAL: FALHA" in capsys.readouterr().out


@pytest.mark.unit
def test_playlist_para_apos_primeiro_bloqueio_temporario(monkeypatch, tmp_path):
    itens = [
        {"title": "Primeira", "url": "id1", "playlist_index": 1},
        {"title": "Segunda", "url": "id2", "playlist_index": 2},
    ]
    chamadas = []
    monkeypatch.setattr(yv, "obter_itens_playlist", lambda *_args: (itens, ""))

    def bloqueada(*args):
        chamadas.append(args[0])
        return yv.ResultadoDownload(falhas=["Primeira: O YouTube bloqueou tentativas temporariamente. Aguarde antes de tentar novamente."])

    monkeypatch.setattr(yv, "baixar_item", bloqueada)
    resultado = yv.baixar_playlist("https://fake/?list=1", tmp_path, True)
    assert chamadas == ["https://www.youtube.com/watch?v=id1"]
    assert len(resultado.falhas) == 1
