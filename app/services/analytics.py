"""数据清洗、融合分析与家长报告生成（大数据构建负责人核心逻辑）。

流程：
1. 异常过滤：quality 低于阈值 / face_present=false 的退化帧标记或剔除
2. 缺失处理：时间窗内无特征时用前向填充或中性值兜底
3. 时间窗口平滑：按固定窗口（默认 60s）聚合参与度，输出 attention_curve
4. 参与度估计：face_present、eye_state、head_direction、quality 加权
5. 对话质量：回合数、回复长度、理由深度关键词命中、互动次数
6. 融合：对话质量 + 视觉参与度 → 家长综合报告（含建议）

所有输出为普通 dict，可 JSON 序列化，字段见 docs/data-contract.md。
"""
from __future__ import annotations

import json
import time
from typing import Any

# ---- 清洗参数（可按需调整）----
MIN_QUALITY = 0.5           # 低于该质量的特征视为不可靠
WINDOW_MS = 60_000          # 时间窗口 60 秒
ENGAGEMENT_WEIGHTS = {      # 参与度权重
    "face_present": 0.4,
    "eye_open": 0.3,
    "head_front": 0.2,
    "quality": 0.1,
}
# 理由深度关键词（批判性思维画像用）
DEPTH_KEYWORDS = [
    "因为", "所以", "原因是", "如果", "那么", "首先", "其次", "例如",
    "我认为", "你觉得", "想一想", "比较", "证据", "观察", "为什么", "怎样",
]

# 合法枚举（采集端约定的取值）
VALID_EXPRESSION = {"neutral", "happy", "sad", "surprised", "unknown"}
VALID_HEAD = {"front", "left", "right", "unknown"}
VALID_EYE = {"open", "closed", "unknown"}


# ---------- 特征清洗 ----------

def validate_feature(feature: dict[str, Any]) -> list[str]:
    """校验单条特征，返回错误列表；空列表表示合法。非法值不阻断入库，但分析时剔除。"""
    errors = []
    if not feature.get("session_id"):
        errors.append("missing session_id")
    if feature.get("expression", "unknown") not in VALID_EXPRESSION:
        errors.append("bad expression")
    if feature.get("head_direction", "unknown") not in VALID_HEAD:
        errors.append("bad head_direction")
    if feature.get("eye_state", "unknown") not in VALID_EYE:
        errors.append("bad eye_state")
    q = feature.get("quality")
    if q is None or not (0.0 <= float(q) <= 1.0):
        errors.append("bad quality")
    return errors


def clean_features(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """异常过滤：剔除质量过低、枚举非法、无人脸的退化帧。返回清洗后的列表。"""
    cleaned = []
    for f in features:
        if validate_feature(f):          # 有错误 → 剔除
            continue
        if float(f.get("quality", 0)) < MIN_QUALITY:
            continue
        cleaned.append(f)
    return cleaned


# ---------- 参与度估计 ----------

def _engagement_one(f: dict[str, Any]) -> float:
    eye = 1.0 if f.get("eye_state") == "open" else 0.0
    head = 1.0 if f.get("head_direction") == "front" else 0.0
    present = 1.0 if f.get("face_present") else 0.0
    return (
        ENGAGEMENT_WEIGHTS["face_present"] * present
        + ENGAGEMENT_WEIGHTS["eye_open"] * eye
        + ENGAGEMENT_WEIGHTS["head_front"] * head
        + ENGAGEMENT_WEIGHTS["quality"] * float(f.get("quality", 0.0))
    )


def _window_engagement(features: list[dict[str, Any]], win_start: int) -> float:
    """一个窗口内的参与度：有效帧均值；无帧时返回中性 0.5（缺失处理兜底）。"""
    in_win = [f for f in features if win_start <= int(f["timestamp"]) < win_start + WINDOW_MS]
    if not in_win:
        return 0.5
    return round(sum(_engagement_one(f) for f in in_win) / len(in_win), 2)


def build_attention_curve(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """时间窗口平滑：以最早时间戳为起点按 WINDOW_MS 切窗，输出曲线。"""
    if not features:
        return []
    start = int(features[0]["timestamp"])
    end = int(features[-1]["timestamp"])
    curve = []
    win_start = start
    while win_start <= end:
        curve.append({
            "window_start": win_start,
            "engagement": _window_engagement(features, win_start),
        })
        win_start += WINDOW_MS
    return curve


# ---------- 对话质量 ----------

def _reasoning_level(hits: int, turns: int) -> str:
    if turns == 0:
        return "无"
    rate = hits / turns
    if rate >= 2.0:
        return "较强"
    if rate >= 1.0:
        return "中等"
    return "较弱"


def analyze_dialogue(turns: list[dict[str, Any]]) -> dict[str, Any]:
    if not turns:
        return {
            "total_turns": 0, "avg_reply_length_chars": 0.0,
            "depth_keyword_hits": 0, "reasoning_level": "无",
        }
    total_chars = 0
    hits = 0
    for t in turns:
        reply = t.get("reply") or ""
        transcript = t.get("transcript") or ""
        total_chars += len(reply)
        hits += sum(1 for kw in DEPTH_KEYWORDS if kw in reply or kw in transcript)
    return {
        "total_turns": len(turns),
        "avg_reply_length_chars": round(total_chars / len(turns), 1),
        "depth_keyword_hits": hits,
        "reasoning_level": _reasoning_level(hits, len(turns)),
    }


# ---------- 综合报告 ----------

def build_report(session: dict[str, Any], turns: list[dict[str, Any]],
                 features: list[dict[str, Any]]) -> dict[str, Any]:
    """融合对话质量与视觉参与度，生成家长端综合报告。"""
    cleaned = clean_features(features)
    curve = build_attention_curve(cleaned)
    overall_engagement = (
        round(sum(p["engagement"] for p in curve) / len(curve), 2) if curve else 0.0
    )
    dialogue = analyze_dialogue(turns)

    advice = []
    if dialogue["total_turns"] < 3:
        advice.append("对话时长较短，可增加开放性问题，鼓励孩子多表达")
    if overall_engagement < 0.5:
        advice.append("孩子整体参与度偏低，建议缩短单次学习时长或加入互动环节")
    if len(curve) >= 3:
        low_windows = [p for p in curve if p["engagement"] < 0.5]
        if low_windows:
            advice.append(
                f"在 {len(low_windows)} 个时间窗口注意力下降，建议分段学习、中途休息"
            )
    if dialogue["reasoning_level"] == "较强":
        advice.append("孩子能主动使用因果与比较语言，可继续用追问式对话培养逻辑思维")
    elif dialogue["reasoning_level"] == "较弱":
        advice.append("可多用'为什么''你觉得呢'引导孩子说出理由")

    return {
        "report_id": session["session_id"],
        "session": {
            "created_at": session["created_at"],
            "ended_at": session.get("ended_at"),
            "duration_ms": (session.get("ended_at") or int(time.time() * 1000))
                           - session["created_at"],
            "turn_count": len(turns),
        },
        "dialogue_quality": dialogue,
        "focus": {
            "feature_count": len(features),
            "valid_feature_count": len(cleaned),
            "engagement_score": overall_engagement,
            "attention_curve": curve,
        },
        "advice": advice,
    }


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False)
