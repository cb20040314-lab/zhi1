"""FastAPI 统一入口：路由注册、静态资源与 health 接口。

运行：uvicorn app.main:app --host 0.0.0.0 --port 8000（树莓派上单 worker 即可）
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import ingest, turn
from .services import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


def _load_dotenv(path: str) -> None:
    """轻量 .env 加载：启动时自动读取项目根目录 .env（密钥文件，已被 git 忽略）。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(os.path.join(os.path.dirname(BASE_DIR), ".env"))

app = FastAPI(title="智能教育机器人后端", version="2.0")

app.include_router(ingest.router)
app.include_router(turn.router)

# 静态音频（Mock TTS 产物）可被手机/家长端直接播放
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "mock": os.getenv("MOCK_AI", "1") == "1",
        "tables_ok": db.check_tables(),
        "db_path": db.DB_PATH,
    }


@app.on_event("startup")
def startup() -> None:
    db.init_db()
