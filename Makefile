.PHONY: dev test app dmg

# `make dev` = `python3 run.py`: installs dependencies on first run, then starts backend + frontend (browser).
dev:
	python3 run.py

# Run after `make dev` has created .venv once.
test:
	cd backend && ../.venv/bin/python -m pytest -q

# Desktop window without packaging (uses .venv and a fresh frontend build).
app:
	cd frontend && npm run build
	cd desktop && (test -d node_modules || npm install) && npm start

# Build the macOS .dmg (run on a Mac). Output: desktop/release/
dmg:
	./desktop/build.sh
