#!/usr/bin/env python3
"""Entrypoint compatível do downloader interativo."""

from music_library.downloader import *
from music_library.downloader import main


if __name__ == "__main__":
    raise SystemExit(main())
