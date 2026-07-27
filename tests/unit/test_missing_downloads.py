from datetime import datetime, timezone

from music_library.history import HistoryStore
from music_library.library import avaliar_album, catalogo_do_album
from music_library.missing_downloads import acao_por_cd, executar_plano, planejar_faixas_faltantes
from music_library.results import ResultadoDownload


def criar_faixas(directory, tracks):
    directory.mkdir(parents=True, exist_ok=True)
    for index, track in enumerate(tracks, 1):
        (directory / f"{index:02d} - {track}.mp3").write_bytes(b"fake")


def test_cd_10_de_12_planeja_exatamente_as_duas_faixas_faltantes(tmp_path):
    album = "2000 - The Sickness"
    tracks = catalogo_do_album("Disturbed", album)["faixas"]
    criar_faixas(tmp_path, [track for track in tracks if track not in {"Voices", "Want"}])

    plan = planejar_faixas_faltantes("Disturbed", album, tmp_path, HistoryStore(tmp_path / "history.sqlite"))

    assert [(item["index"], item["track"]) for item in plan] == [(1, "Voices"), (8, "Want")]
    assert all(item["kind"] == "individual" for item in plan)


def test_cd_completo_14_de_14_nao_tem_plano_de_download(tmp_path):
    album = "2005 - Ten Thousand Fists"
    criar_faixas(tmp_path, catalogo_do_album("Disturbed", album)["faixas"])

    assert planejar_faixas_faltantes("Disturbed", album, tmp_path) == []
    assert acao_por_cd(avaliar_album("Disturbed", album, tmp_path), True, True)["tipo"] == "completo"


def test_plano_nao_duplica_mp3_que_ja_existe(tmp_path):
    criar_faixas(tmp_path, ["Voices"])
    chamadas = []
    plan = [{"artist": "Disturbed", "album": "2000 - The Sickness", "track": "Voices", "index": 1, "url": "https://youtu.be/a", "kind": "individual", "candidate_id": None}]

    result = executar_plano(plan, tmp_path, lambda *_: chamadas.append(True))

    assert chamadas == []
    assert result == {"baixadas": [], "faltando": [], "falhas": [], "alternativas": []}


def test_falha_do_plano_bloqueia_mesma_url_por_30_dias(tmp_path):
    history = HistoryStore(tmp_path / "history.sqlite")
    candidate = history.add_candidate("Disturbed", "2000 - The Sickness", "Voices", "https://youtu.be/a", "CATALOGO_OFICIAL")
    plan = [{"artist": "Disturbed", "album": "2000 - The Sickness", "track": "Voices", "index": 1, "url": "https://youtu.be/a", "kind": "individual", "candidate_id": candidate}]

    result = executar_plano(plan, tmp_path, lambda *_: ResultadoDownload(falhas=["Voices: fonte indisponível"]), history)

    assert result["faltando"] == ["Voices"]
    assert not history.can_attempt(candidate, datetime.now(timezone.utc))
    attempt = history.history()[0]
    assert attempt["result"] == "FALHA"
    assert attempt["technical_message"]


def test_sucesso_atualiza_progresso_sem_rebaixar_existentes(tmp_path):
    album = "2000 - The Sickness"
    tracks = catalogo_do_album("Disturbed", album)["faixas"]
    criar_faixas(tmp_path, [track for track in tracks if track not in {"Voices", "Want"}])
    plan = planejar_faixas_faltantes("Disturbed", album, tmp_path)

    def download_fake(item, directory):
        file = directory / f"{item['index']:02d} - {item['track']}.mp3"
        file.write_bytes(b"fake")
        return ResultadoDownload(arquivos=[file])

    result = executar_plano(plan, tmp_path, download_fake)

    assert result["baixadas"] == ["Voices", "Want"]
    assert avaliar_album("Disturbed", album, tmp_path)["Progresso"] == "12 / 12"


def test_botao_correto_para_cd_vazio_incompleto_completo_e_sem_fonte():
    assert acao_por_cd({"Status": "Sem faixas"}, True, True)["texto"] == "Baixar CD completo"
    assert acao_por_cd({"Status": "Incompleto", "faltantes": ["A", "B"]}, True, True)["texto"] == "Baixar músicas faltantes (2)"
    completo = acao_por_cd({"Status": "Completo"}, True, True)
    assert completo["texto"] == "CD completo" and completo["desabilitado"]
    sem_fonte = acao_por_cd({"Status": "Sem catálogo"}, False, False)
    assert sem_fonte["texto"] == "Fonte do CD não cadastrada" and sem_fonte["desabilitado"]
    assert acao_por_cd({"Status": "Incompleto", "faltantes": []}, True, True)["texto"] == "Sem faixas faltantes"


def test_falha_da_primeira_fonte_tenta_a_proxima_e_bloqueia_so_a_primeira(tmp_path):
    history = HistoryStore(tmp_path / "history.sqlite")
    primeira = history.add_candidate("Disturbed", "2000 - The Sickness", "Voices", "https://www.youtube.com/watch?v=primeira", "MANUAL", priority=1)
    segunda = history.add_candidate("Disturbed", "2000 - The Sickness", "Voices", "https://www.youtube.com/watch?v=segunda", "MANUAL", priority=2)
    plan = [{"artist": "Disturbed", "album": "2000 - The Sickness", "track": "Voices", "index": 1, "url": "https://www.youtube.com/watch?v=primeira", "kind": "individual", "candidate_id": primeira, "sources": [{"url": "https://www.youtube.com/watch?v=primeira", "candidate_id": primeira}, {"url": "https://www.youtube.com/watch?v=segunda", "candidate_id": segunda}]}]
    chamadas = []

    def download_fake(item, directory):
        chamadas.append(item["url"])
        if item["candidate_id"] == primeira:
            return ResultadoDownload(falhas=["fonte indisponível"])
        arquivo = directory / "01 - Voices.mp3"
        arquivo.write_bytes(b"fake")
        return ResultadoDownload(arquivos=[arquivo])

    result = executar_plano(plan, tmp_path, download_fake, history)

    assert chamadas == ["https://www.youtube.com/watch?v=primeira", "https://www.youtube.com/watch?v=segunda"]
    assert result["baixadas"] == ["Voices"]
    assert not history.can_attempt(primeira)
    assert history.sources("Disturbed", "2000 - The Sickness", "Voices")[0]["next_retry_at"]
