import subprocess
import urllib.request

import pytest


@pytest.mark.integration
def test_compose_e_servico_local_disponivel():
    config = subprocess.run(["docker", "compose", "config"], check=True, capture_output=True, text=True)
    assert "musica-library" in config.stdout
    subprocess.run(["docker", "image", "inspect", "scriptdownloadytb-musica-library"], check=True, capture_output=True)
    with urllib.request.urlopen("http://127.0.0.1:8507/_stcore/health", timeout=5) as resposta:
        assert resposta.read() == b"ok"
