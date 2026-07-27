from datetime import datetime, timezone

from music_library.history import HistoryStore, normalizar_url_youtube
from music_library.track_sources import best_source


def test_preenchimento_automatico_e_bloqueio_da_url(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite")
    source = best_source("Disturbed", "2000 - The Sickness", "Voices", store)
    assert source["url"] == "https://www.youtube.com/watch?v=U5RzmXirUbY"
    store.record_attempt(source["candidate_id"], "FALHA", "HTTP_429", "bloqueio", datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert best_source("Disturbed", "2000 - The Sickness", "Voices", store, datetime(2026, 1, 2, tzinfo=timezone.utc)) is None


def test_want_e_origem_antiga_sem_registro(tmp_path):
    source = best_source("Disturbed", "2000 - The Sickness", "Want")
    assert source["title"] == "Want"
    store = HistoryStore(tmp_path / "history.sqlite")
    assert store.sources("Disturbed", "2000 - The Sickness", "The Game") == []


def test_url_de_radio_normaliza_e_mesmo_video_nao_cria_alternativa(tmp_path):
    radio = "https://www.youtube.com/watch?v=U5RzmXirUbY&list=RDU5RzmXirUbY&start_radio=1"
    canonical = "https://www.youtube.com/watch?v=U5RzmXirUbY"
    assert normalizar_url_youtube(radio) == canonical
    store = HistoryStore(tmp_path / "history.sqlite")
    primeiro = store.add_candidate("Disturbed", "2000 - The Sickness", "Voices", radio)
    repetido = store.add_candidate("Disturbed", "2000 - The Sickness", "Voices", canonical)
    assert primeiro == repetido
    assert len(store.sources("Disturbed", "2000 - The Sickness", "Voices")) == 1


def test_video_id_diferente_cria_fonte_alternativa(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite")
    primeiro = store.add_candidate("Disturbed", "2000 - The Sickness", "Voices", "https://www.youtube.com/watch?v=U5RzmXirUbY")
    alternativa = store.add_candidate("Disturbed", "2000 - The Sickness", "Voices", "https://www.youtube.com/watch?v=OutroVideo")
    fontes = store.sources("Disturbed", "2000 - The Sickness", "Voices")
    assert primeiro != alternativa
    assert [fonte["video_id"] for fonte in fontes] == ["U5RzmXirUbY", "OutroVideo"]
