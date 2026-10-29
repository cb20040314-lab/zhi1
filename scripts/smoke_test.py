"""端到端冒烟测试：按数据负责人验收标准执行。

流程：创建会话 → 连续上传 3 段音频 → 上传 20 条特征 → 结束会话 → 查询报告。
用法：python scripts/smoke_test.py [base_url] [session_id]
退出码 0 = 全部通过。
"""
from __future__ import annotations

import io
import math
import struct
import sys
import time
import wave

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
SESSION_ID = sys.argv[2] if len(sys.argv) > 2 else ""

EXPRESSIONS = ["neutral", "happy", "neutral", "surprised", "neutral", "sad", "neutral", "happy"]
HEAD = ["front", "front", "left", "front", "front", "right", "front", "front"]
EYE = ["open", "open", "open", "open", "closed", "open", "open", "open"]


def make_wav(seconds: float = 1.0, freq: int = 440) -> bytes:
    """生成与 Mock TTS 相同规格的占位 wav 作为上传音频。"""
    rate = 8000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * seconds)):
            v = int(12000 * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def step(name: str, ok: bool, extra: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{(' - ' + extra) if extra else ''}")
    if not ok:
        sys.exit(1)


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=30)

    print(f"== 冒烟测试: {BASE} ==")

    # 1. health
    r = client.get("/api/health")
    step("health", r.status_code == 200 and r.json().get("status") == "ok", str(r.json()))

    # 2. 创建会话
    payload = {"session_id": SESSION_ID} if SESSION_ID else {}
    r = client.post("/api/session/start", json=payload)
    step("session/start", r.status_code == 200)
    sid = r.json()["session_id"]
    print(f"   session_id = {sid}")

    # 3. 连续上传 3 段音频
    turns = []
    for i in range(3):
        r = client.post(
            "/api/turn",
            data={"session_id": sid},
            files={"audio": ("turn.wav", make_wav(1.0, 300 + i * 60), "audio/wav")},
        )
        ok = r.status_code == 200 and r.json().get("transcript") and r.json().get("reply")
        step(f"turn {i + 1}", ok, str(r.json() if ok else r.text))
        turns.append(r.json())

    # 4. 上传 20 条特征（模拟 20 秒采样，含部分低质量/缺席帧）
    for i in range(20):
        present = i % 5 != 3                     # 第 3、8、13、18 条为缺席
        r = client.post("/api/focus", json={
            "session_id": sid,
            "timestamp": int(time.time() * 1000) + i * 1000,
            "face_present": present,
            "expression": EXPRESSIONS[i % len(EXPRESSIONS)],
            "head_direction": HEAD[i % len(HEAD)],
            "eye_state": EYE[i % len(EYE)],
            "quality": 0.4 if i in (7, 19) else round(0.6 + (i % 5) * 0.08, 2),
        })
        if r.status_code != 200:
            step(f"focus {i + 1}", False, r.text)
    step("focus x20", True, "已连续上传 20 条特征")

    # 5. 结束会话
    r = client.post("/api/session/end", json={"session_id": sid})
    step("session/end", r.status_code == 200, str(r.json()))

    # 6. 查询报告
    r = client.get(f"/api/report/{sid}")
    step("report", r.status_code == 200, "")
    rep = r.json()
    dq = rep.get("dialogue_quality", {})
    fo = rep.get("focus", {})
    print(f"   回合数={dq.get('total_turns')} 理由深度={dq.get('reasoning_level')} "
          f"有效特征={fo.get('valid_feature_count')}/{fo.get('feature_count')} "
          f"参与度={fo.get('engagement_score')} 曲线窗口数={len(fo.get('attention_curve', []))}")
    step("report 内容完整", rep.get("report_id") == sid and dq and fo.get("attention_curve"))

    print("== 全部通过 ==")


if __name__ == "__main__":
    main()
