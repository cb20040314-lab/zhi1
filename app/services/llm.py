"""LLM 服务适配：根据上下文生成教育机器人回复。

Mock 模式：按回合返回预置的教育回复。
真实模式：调用外部 LLM（如 OpenAI 兼容接口），密钥只从环境变量读取（LLM_API_KEY、
LLM_BASE_URL、LLM_MODEL），固定超时 + 一次重试。
"""
from __future__ import annotations

import os

from .errors import AIServiceError

# Mock 回复（与 asr.MOCK_TRANSCRIPTS 配套）
MOCK_REPLIES = [
    "天空看起来是蓝色的，是因为阳光中的蓝光波长较短，容易被空气分子散射到各个方向，所以我们抬头看到的天空主要是蓝色的。",
    "太阳不会真的'升起和落下'，而是地球在自转。我们所在的这一面转向太阳时，就看到日出；转开时，就看到日落。",
    "星星其实是遥远的太阳。它们离我们很远很远，所以看起来只是一小点亮光。古人把星星连成图案，就编出了许多神话故事。",
    "月亮的形状变化是因为它绕地球转动时，我们只能看到被阳光照亮的那一部分。弯弯的月亮叫蛾眉月，是月初或月末常见的形状。",
    "蜜蜂采蜜时会把花蜜吸进肚子里，带回蜂巢后吐出来反复酿造，水分蒸发后就变成了蜂蜜。它们也是植物授粉的重要帮手。",
]


def _is_mock() -> bool:
    return os.getenv("MOCK_AI", "1") == "1"


def generate_reply(transcript: str, history: list[dict], turn_index: int) -> str:
    """入参：用户文本、历史回合（[{transcript, reply}]）、回合序号。返回回复文本。"""
    if _is_mock():
        return MOCK_REPLIES[turn_index % len(MOCK_REPLIES)]

    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    if not api_key:
        raise AIServiceError("LLM_API_KEY 未设置")

    # 组装带教育角色的提示词（保留结构化画像所需的理由深度引导）
    system = (
        "你是面向小学生的教育机器人助手。回答要准确、通俗、有鼓励性，"
        "并适当追问或给出一个思考题，帮助孩子培养批判性思维。"
    )
    messages = [{"role": "system", "content": system}]
    for h in history:
        messages.append({"role": "user", "content": h["transcript"]})
        messages.append({"role": "assistant", "content": h["reply"]})
    messages.append({"role": "user", "content": transcript})

    # ---- 真实 LLM 适配点：超时 + 一次重试 ----
    # try:
    #     resp = httpx.post(f"{base_url}/chat/completions", headers={...},
    #                       json={"model": model, "messages": messages}, timeout=20)
    #     resp.raise_for_status()
    #     return resp.json()["choices"][0]["message"]["content"]
    # except httpx.TimeoutException:
    #     raise AIServiceError("AI_TIMEOUT", "LLM 请求超时")
    # except Exception:
    #     raise AIServiceError("AI_ERROR", "LLM 请求失败")
    raise AIServiceError("LLM_API_KEY 未设置且未实现真实 LLM 适配")
