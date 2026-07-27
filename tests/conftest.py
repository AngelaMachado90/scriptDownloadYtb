import socket

import pytest


@pytest.fixture(autouse=True)
def bloquear_rede(monkeypatch):
    original = socket.socket.connect

    def sem_rede(*_args, **_kwargs):
        endereco = _args[1] if len(_args) > 1 else _kwargs.get("address")
        if endereco and endereco[0] in {"127.0.0.1", "::1"}:
            return original(*_args, **_kwargs)
        raise AssertionError("A suíte de testes não permite acesso à rede.")

    monkeypatch.setattr(socket.socket, "connect", sem_rede)
