.PHONY: test-unit test-integration test check

test-unit:
	python3 -m pytest tests/unit --cov=music_library.downloader --cov=app --cov-report=term-missing

test-integration:
	python3 -m pytest tests/integration --cov=music_library.downloader --cov=app --cov-report=term-missing

test:
	python3 -m pytest --cov=music_library.downloader --cov=app --cov-report=term-missing

check: test
	python3 -m py_compile youtubeVideos.py app.py scripts/validar_ytdlp.py music_library/*.py
	docker compose config
	git diff --check
