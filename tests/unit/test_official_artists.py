from music_library.official_artists import artista_oficial, busca_oficial, url_pertence_ao_canal


def test_disturbed_e_jonas_tem_prioridade_oficial():
    assert artista_oficial("Disturbed")["youtube_channel"].endswith("UCveWMJeHgcIUPMnFzd7Vxjg")
    assert artista_oficial("Jonas Brothers")["official_site"] == "https://jonasbrothers.com/"
    assert "Disturbed+Voices+official+audio" in busca_oficial("Disturbed", "Voices")


def test_selo_e_verificacao_somente_para_canal_cadastrado():
    canal = "https://www.youtube.com/channel/UCveWMJeHgcIUPMnFzd7Vxjg/videos"
    assert url_pertence_ao_canal(canal, "Disturbed")
    assert not url_pertence_ao_canal("https://www.youtube.com/watch?v=externo", "Disturbed")
    assert artista_oficial("Outra Banda") is None
