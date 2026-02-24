#!/usr/bin/env python3
"""Запуск админ-панели (FastAPI)."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.admin.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
