"""Entry point used by the desktop app (and its PyInstaller bundle): `desktop_server --port 8765`."""
import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    import uvicorn

    from app.main import app

    # Bound to localhost only: the app is not reachable from the network.
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    sys.exit(main())
