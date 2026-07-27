from datetime import datetime, timedelta, timezone

from music_library.history import HistoryStore


def test_falha_bloqueia_url_por_30_dias_e_url_diferente_permite(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite")
    agora = datetime(2026, 1, 1, tzinfo=timezone.utc)
    primeira = store.add_candidate("Disturbed", "2000 - The Sickness", "Voices", "https://youtu.be/a", "MANUAL")
    store.record_attempt(primeira, "FALHA", "HTTP_429", "cookie=segredo", agora)
    assert not store.can_attempt(primeira, agora + timedelta(days=29))
    store.record_attempt(primeira, "FALHA", "HTTP_429", "nova", agora + timedelta(days=1))
    assert store.sources("Disturbed", "2000 - The Sickness", "Voices")[-1]["result"] == "BLOQUEADA"
    assert store.can_attempt(primeira, agora + timedelta(days=30))
    alternativa = store.add_candidate("Disturbed", "2000 - The Sickness", "Voices", "https://youtu.be/b", "BUSCA_MANUAL")
    assert store.can_attempt(alternativa, agora + timedelta(days=1))


def test_sucesso_encerra_pendencia_e_segredos_nao_entram_no_banco(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite")
    candidate = store.add_candidate("Disturbed", "2000 - The Sickness", "Want", "https://site/video?token=segredo", "CATALOGO_OFICIAL")
    store.record_attempt(candidate, "SUCESSO", "UNKNOWN", "Authorization: Bearer segredo")
    fonte = store.sources("Disturbed", "2000 - The Sickness", "Want")[0]
    assert "token" not in fonte["url"] and "segredo" not in fonte["message"]
    assert not store.can_attempt(candidate)


def test_falha_persiste_historico_com_proxima_tentativa(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite")
    candidate = store.add_candidate("Disturbed", "2000 - The Sickness", "Voices", "https://youtu.be/falha")
    store.record_attempt(candidate, "FALHA", "PRIVATE", "detalhe técnico")
    registro = store.history()[0]
    assert registro["result"] == "FALHA"
    assert registro["error_category"] == "PRIVATE"
    assert registro["next_retry_at"]
