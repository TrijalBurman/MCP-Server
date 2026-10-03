from __future__ import annotations

import argparse

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run your local knowledge copilot")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run("copilot.api:app", host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
