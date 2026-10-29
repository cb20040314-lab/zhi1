"""会话与特征接收接口：session start/end、focus（数据契约 3.2/3.4/3.5）。"""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from ..services import analytics, db

router = APIRouter(prefix="/api", tags=["ingest"])

SESSION_ID_PATTERN_OK = lambda sid: isinstance(sid, str) and len(sid) <= 64 and sid.strip() != ""


@router.post("/session/start")
def session_start(payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    payload = payload or {}
    sid = payload.get("session_id")
    if sid is not None and not SESSION_ID_PATTERN_OK(sid):
        raise HTTPException(400, {"code": "INVALID_SESSION", "message": "session_id 格式非法"})
    if sid and db.get_session(sid):
        raise HTTPException(400, {"code": "INVALID_SESSION", "message": "session_id 已存在"})
    return db.new_session(sid)


@router.post("/session/end")
def session_end(payload: dict[str, Any]) -> dict[str, Any]:
    sid = (payload or {}).get("session_id", "")
    session = db.get_session(sid) if SESSION_ID_PATTERN_OK(sid) else None
    if not session:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "会话不存在"})
    if session["status"] == "ended":
        raise HTTPException(400, {"code": "INVALID_SESSION", "message": "会话已结束"})

    turns = db.list_turns(sid)
    features = db.list_face_features(sid)
    now = int(time.time() * 1000)
    report = analytics.build_report({**session, "ended_at": now}, turns, features)
    db.end_session(sid, analytics.to_json(report))
    return {
        "session_id": sid,
        "status": "ended",
        "ended_at": now,
        "report_id": sid,
    }


@router.post("/focus")
def focus(feature: dict[str, Any]) -> dict[str, Any]:
    sid = feature.get("session_id", "")
    session = db.get_session(sid) if SESSION_ID_PATTERN_OK(sid) else None
    if not session:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "会话不存在"})
    if session["status"] != "active":
        raise HTTPException(400, {"code": "INVALID_SESSION", "message": "会话已结束，不再接收特征"})

    # 非法枚举/质量不阻断入库（由 analytics 分析时剔除），但字段缺失需要兜底
    errors = analytics.validate_feature(feature)
    if errors and "missing session_id" in errors:
        raise HTTPException(400, {"code": "INVALID_SESSION", "message": "缺少 session_id"})

    db.add_face_feature(feature)
    return {"ok": True, "received": db.count_face_features(sid)}


@router.get("/report/{report_id}")
def report(report_id: str) -> dict[str, Any]:
    session = db.get_session(report_id) if SESSION_ID_PATTERN_OK(report_id) else None
    if not session:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "会话不存在"})
    if session["status"] != "ended":
        # 未结束时也可返回实时报告，画像基于当前数据
        turns = db.list_turns(report_id)
        features = db.list_face_features(report_id)
        report = analytics.build_report(session, turns, features)
        return report
    import json as _json
    return _json.loads(session["summary"])
