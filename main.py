"""Entry point: run the API server + background issue watcher."""

from __future__ import annotations

import asyncio
import logging
import sys

import uvicorn

from core.config import get_settings


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    port = 9000
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=", 1)[1])
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=port,
        reload="--reload" in sys.argv,
    )


if __name__ == "__main__":
    main()
