from music_library.library import avaliar_album, filtrar_biblioteca


def criar_faixas(diretorio, faixas):
    diretorio.mkdir(parents=True, exist_ok=True)
    for indice, faixa in enumerate(faixas, 1):
        (diretorio / f"{indice:02d} - {faixa}.mp3").write_bytes(b"fake")


def test_the_sickness_reconhece_faixas_faltantes(tmp_path):
    criar_faixas(tmp_path, ["The Game", "Stupify", "Down with the Sickness", "Violence Fetish", "Fear", "Numb", "Conflict", "Shout 2000", "Droppin' Plates", "Meaning of Life"])
    resultado = avaliar_album("Disturbed", "2000 - The Sickness", tmp_path)
    assert resultado["Progresso"] == "10 / 12"
    assert resultado["faltantes"] == ["Voices", "Want"]


def test_completo_duplicado_sem_catalogo_e_filtros(tmp_path):
    faixas = ["Voices", "The Game", "Stupify", "Down with the Sickness", "Violence Fetish", "Fear", "Numb", "Want", "Conflict", "Shout 2000", "Droppin' Plates", "Meaning of Life"]
    criar_faixas(tmp_path / "completo", faixas)
    assert avaliar_album("Disturbed", "2000 - The Sickness", tmp_path / "completo")["Status"] == "Completo"
    criar_faixas(tmp_path / "errado", faixas[:-1] + ["Voices"])
    errado = avaliar_album("Disturbed", "2000 - The Sickness", tmp_path / "errado")
    assert errado["Status"] == "Incompleto" and "Meaning of Life" in errado["faltantes"] and errado["duplicatas"]
    assert avaliar_album("Outra", "Album", tmp_path)["Status"] == "Sem catálogo"
    registros = [{"Artista": "Disturbed", "CD": "A"}, {"Artista": "Outra", "CD": "B"}]
    assert filtrar_biblioteca(registros, "Disturbed") == [registros[0]]
    assert filtrar_biblioteca(registros, cd="B") == [registros[1]]


def test_evolution_reconhece_nomes_de_videos_oficiais(tmp_path):
    faixas = ["Are You Ready", "No More", "A Reason to Fight", "In Another Time", "Stronger on Your Own", "Hold on to Memories", "Saviour of Nothing", "Watch You Burn", "The Best Ones Lie", "Already Gone"]
    for faixa in faixas:
        (tmp_path / f"Disturbed - {faixa} [Official Music Video].mp3").write_bytes(b"fake")
    assert avaliar_album("Disturbed", "2018 - Evolution", tmp_path)["Progresso"] == "10 / 10"


def test_the_sickness_reconhece_sufixos_de_upgrade_sem_rebaixar(tmp_path):
    faixas = ["Voices", "The Game", "Stupify", "Down with the Sickness", "Violence Fetish", "Fear", "Numb", "Want", "Conflict", "Shout 2000", "Droppin' Plates", "Meaning of Life"]
    criar_faixas(tmp_path, faixas[1:7] + faixas[8:])
    (tmp_path / "01 - Disturbed - Voices (Official Music Video) [4K Upgrade].mp3").write_bytes(b"fake")
    (tmp_path / "08 - Disturbed - Want (Official Music Video) [HD Upgrade].mp3").write_bytes(b"fake")
    resultado = avaliar_album("Disturbed", "2000 - The Sickness", tmp_path)
    assert resultado["Progresso"] == "12 / 12"
    assert resultado["faltantes"] == []
