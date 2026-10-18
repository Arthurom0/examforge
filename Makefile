.PHONY: dev test

# `make dev` = `python3 run.py`: installs dependencies on first run, then starts backend + frontend.
dev:
	python3 run.py

# Run after `make dev` has created .venv once.
test:
	cd backend && ../.venv/bin/python -m pytest -q
