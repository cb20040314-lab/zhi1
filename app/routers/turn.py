"""语音回合接口：POST /api/turn（数据契约 3.3）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..services import asr, db, llm, tts
from ..services.errors import AIServiceError

router = APIRouter(prefix="/api", tags=["turn"])

MAX_AUDIO_BYTES = 15 * 1024 * 1024  # 15MB 上限（演示版音频 3~8 秒，远小于该值）


@router.post("/turn")
async def turn(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    turn: str = Form(default=""),
) -> dict[str, Any]:
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "会话不存在"})
    if session["status"] != "active":
        raise HTTPException(400, {"code": "INVALID_SESSION", "message": "会话已结束，不再接收音频"})

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, {"code": "AUDIO_REQUIRED", "message": "未收到音频文件"})
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(400, {"code": "AUDIO_TOO_LONG", "message": "音频超过 15MB 上限"})

    # 回合序号：客户端可自定，缺省服务端自增
    turn_no = int(turn) if turn.strip().isdigit() else db.next_turn_no(session_id)

    history = [
        {"transcript": t["transcript"], "reply": t["reply"]}
        for t in db.list_turns(session_id)
    ]
    mime = audio.content_type or "audio/webm"

    try:
        transcript = asr.transcribe(audio_bytes, turn_no - 1, mime=mime)
        reply = llm.generate_reply(transcript, history, turn_no - 1)
        audio_url = tts.synthesize(reply, turn_no)
    except AIServiceError as e:
        # 演示版允许单回合失败，但记录状态，不阻塞会话
        db.add_turn(session_id, turn_no, "", "", "", status=e.code.lower())
        raise HTTPException(502, {"code": e.code, "message": e.message})

    db.add_turn(session_id, turn_no, transcript, reply, audio_url, status="ok")
    return {
        "session_id": session_id,
        "turn": turn_no,
        "transcript": transcript,
        "reply": reply,
        "audio_url": audio_url,
        "status": "ok",
    }
