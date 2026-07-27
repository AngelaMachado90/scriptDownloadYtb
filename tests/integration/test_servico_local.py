import subprocess
import urllib.request

import pytest


@pytest.mark.integration
def test_compose_limita_porta_ao_loopback_do_servidor():
    config = subprocess.run(["docker", "compose", "config"], check=True, capture_output=True, text=True)
    assert "musica-library" in config.stdout
    assert 'host_ip: 127.0.0.1' in config.stdout
    assert 'published: "8507"' in config.stdout
    assert 'target: 8501' in config.stdout
    assert "0.0.0.0" not in config.stdout


@pytest.mark.integration
def test_healthcheck_esta_saudavel_no_servidor():
    subprocess.run(["docker", "image", "inspect", "scriptdownloadytb-musica-library"], check=True, capture_output=True)
    with urllib.request.urlopen("http://127.0.0.1:8507/_stcore/health", timeout=5) as resposta:
        assert resposta.read() == b"ok"


@pytest.mark.integration
def test_container_inclui_catalogos_versionados():
    """Evita imagem saudável que falha ao renderizar a tela por falta de data/."""
    resultado = subprocess.run(
        [
            "docker", "exec", "musica-library", "python", "-c",
            "from pathlib import Path; "
            "assert all((Path('/app/data') / name).is_file() for name in "
            "('album_sources.json', 'official_artists.json', 'track_sources.json'))",
        ],
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr


@pytest.mark.acceptance
def test_acesso_windows_por_vscode_e_manual():
    """O usuário confirma no Windows após encaminhar 8507 pela aba PORTS do VS Code."""
    pytest.skip("Aceitação manual: o navegador cliente não é alcançável pelo servidor.")
