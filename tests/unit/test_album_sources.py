from music_library.album_sources import albums_for_artist, best_album_source
from music_library.downloader import eh_playlist


def test_jonas_preenchimento_automatico_de_playlist():
    source = best_album_source("Jonas Brothers", "2023 - The Album")
    assert source["type"] == "album_playlist"
    assert source["url"].endswith("list=PLxA687tYuMWiTlscgQ2EowZAmBecEwwrS")
    assert "2019 - Happiness Begins" in albums_for_artist("Jonas Brothers")


def test_watch_com_list_e_playlist():
    assert eh_playlist("https://www.youtube.com/watch?v=1E8V-HIIJ30&list=PLxA687tYuMWiTlscgQ2EowZAmBecEwwrS")
