# 智能教育机器人 — 数据契约（data-contract）

> 版本：v2.0 ｜ 冻结时间：2026-10-29 开工后 2 小时内 ｜ 维护人：大数据构建负责人
>
> 任何字段、接口或 Mock 数据的变更，必须先修改本文档，再由各实现方同步提交。三方只以本文档为唯一接口依据。

## 1. 总览

- 演示版平台：树莓派 3（本地 Windows 开发环境亦可运行）
- 技术栈：Python 3.10+ / FastAPI / SQLite（标准库 sqlite3）
- 部署形态：单个 FastAPI worker（`uvicorn app.main:app --port 8000`），不加载本地大模型
- 数据流：采集（手机）→ 本服务（树莓派）→ 客户端（手机页 + 家长页）
- Mock 模式：`MOCK_AI=1` 时 ASR/LLM/TTS 返回预置内容，不请求外部服务；关闭则走真实适配（密钥从环境变量读取）

## 2. 数据库实体（SQLite，字段保留 PostgreSQL 迁移空间）

> 迁移提示：所有时间统一存**毫秒级整数时间戳**（PostgreSQL 可用 `BIGINT` 或转 `TIMESTAMPTZ`）；主键为 TEXT（UUID），便于分布式/数据仓库迁移。

### 2.1 sessions（会话）

| 字段 | 类型 | 说明 |
|---|---|---|
| session_id | TEXT PK | 客户端生成或服务端生成，如 `s_<16位hex>` |
| created_at | INTEGER | 创建时间戳（ms） |
| ended_at | INTEGER NULL | 结束时间戳（ms），未结束为 NULL |
| status | TEXT | `active` / `ended` |
| summary | TEXT NULL | 结束画像 JSON（analytics 生成） |

### 2.2 turns（语音回合）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | 内部自增 |
| session_id | TEXT FK → sessions | 所属会话 |
| turn_no | INTEGER | 回合序号（从 1 开始） |
| transcript | TEXT | ASR 识别文本 |
| reply | TEXT | LLM 回复文本 |
| audio_path | TEXT | TTS 音频相对路径（如 `/static/audio/turn_1.wav`） |
| status | TEXT | `ok` / `asr_failed` / `llm_failed` / `tts_failed` |
| created_at | INTEGER | 时间戳（ms） |

### 2.3 face_features（人脸特征事件）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | 内部自增 |
| session_id | TEXT FK → sessions | 所属会话 |
| timestamp | INTEGER | 特征采样时间戳（ms） |
| face_present | INTEGER | 0/1 人脸是否出现 |
| expression | TEXT | `neutral/happy/sad/surprised/unknown` |
| head_direction | TEXT | `front/left/right/unknown` |
| eye_state | TEXT | `open/closed/unknown` |
| quality | REAL | 采样质量 0~1 |
| raw | TEXT NULL | 原始载荷 JSON（留档，不含图像内容） |

## 3. HTTP 接口（Base URL：`http://<树莓派IP>:8000`）

### 3.1 `GET /api/health`

返回服务与数据库状态。

```json
{
  "status": "ok",
  "mock": true,
  "tables_ok": true
}
```

### 3.2 `POST /api/session/start`

创建会话。请求体可为空，或携带 `{"session_id": "s_xxx"}`（客户端自定义时）。

```json
// 响应 200
{ "session_id": "s_3f2a1b9c", "status": "active", "created_at": 1760000000000 }
```

### 3.3 `POST /api/turn`

上传一段音频（multipart/form-data），返回识别文本、回复与 TTS 音频地址。

| 表单字段 | 类型 | 说明 |
|---|---|---|
| session_id | text | 会话 ID |
| audio | file | 3~8 秒 webm/opus（也可 wav） |
| turn | text 可选 | 调用方自定序号，缺省按服务端自增 |

```json
// 响应 200
{
  "session_id": "s_3f2a1b9c",
  "turn": 2,
  "transcript": "我想了解为什么天空是蓝色的",
  "reply": "天空是蓝色的，是因为阳光中的蓝光被空气分子散射……",
  "audio_url": "/static/audio/turn_2.wav",
  "status": "ok"
}
```

### 3.4 `POST /api/focus`

保存单条人脸特征（application/json）。

```json
// 请求体（人脸特征统一结构，不含图像）
{
  "session_id": "s_3f2a1b9c",
  "timestamp": 1760001000000,
  "face_present": true,
  "expression": "neutral",
  "head_direction": "front",
  "eye_state": "open",
  "quality": 0.86
}
```

```json
// 响应 200
{ "ok": true, "received": 12 }
```

### 3.5 `POST /api/session/end`

结束会话并生成画像。请求体：`{"session_id": "s_xxx"}`。

```json
// 响应 200
{
  "session_id": "s_3f2a1b9c",
  "status": "ended",
  "ended_at": 1760003600000,
  "report_id": "s_3f2a1b9c"
}
```

### 3.6 `GET /api/report/{report_id}`

返回对话画像 + 专注度综合报告。

```json
{
  "report_id": "s_3f2a1b9c",
  "session": {
    "created_at": 1760000000000,
    "ended_at": 1760003600000,
    "duration_ms": 3600000,
    "turn_count": 5
  },
  "dialogue_quality": {
    "total_turns": 5,
    "avg_reply_length_chars": 82.4,
    "depth_keyword_hits": 7,
    "reasoning_level": "中等"
  },
  "focus": {
    "feature_count": 20,
    "valid_feature_count": 18,
    "engagement_score": 0.78,
    "attention_curve": [
      { "window_start": 1760000000000, "engagement": 0.75 },
      { "window_start": 1760000600000, "engagement": 0.80 }
    ]
  },
  "advice": ["对话时长较短，可增加开放性问题", "孩子在 3 个时间窗口注意力下降，建议分段学习"]
}
```

### 3.7 错误码（统一响应结构）

```json
{ "detail": { "code": "SESSION_NOT_FOUND", "message": "会话不存在" } }
```

| code | HTTP | 含义 |
|---|---|---|
| SESSION_NOT_FOUND | 404 | 会话不存在或已结束 |
| INVALID_SESSION | 400 | session_id 格式非法 |
| AUDIO_REQUIRED | 400 | 未收到音频文件 |
| AUDIO_TOO_LONG | 400 | 音频超过 15 秒 |
| AI_TIMEOUT | 502 | ASR/LLM/TTS 超时 |
| AI_ERROR | 502 | AI 服务返回错误 |
| INTERNAL | 500 | 未预期错误 |

## 4. Mock 模式约定

- `MOCK_AI=1`（默认）：`/api/turn` 无需真实密钥即可返回多轮回复。
- Mock 回复按回合数轮换 5 组预置问答（见 `scripts/smoke_test.py` 样例），TTS 返回 `/static/audio/mock_turn_{n}.wav`。
- Mock 音频由 `scripts/gen_mock_audio.py` 生成（1 kHz 正弦波占位，证明链路通即可，演示时替换为真实 TTS）。

## 5. 演示验收样例（数据负责人标准）

```bash
# 1. 启动
uvicorn app.main:app --port 8000

# 2. 创建会话
curl -X POST http://localhost:8000/api/session/start -H "Content-Type: application/json" -d '{}'
# → { "session_id": "s_xxx", "status": "active", ... }

# 3. 连续上传 3 段音频
curl -X POST http://localhost:8000/api/turn -F "session_id=s_xxx" -F "audio=@test.wav"
curl -X POST http://localhost:8000/api/turn -F "session_id=s_xxx" -F "audio=@test.wav"
curl -X POST http://localhost:8000/api/turn -F "session_id=s_xxx" -F "audio=@test.wav"

# 4. 上传 20 条特征（scripts/smoke_test.py 自动做）
# 5. 结束会话并查询报告
curl -X POST http://localhost:8000/api/session/end -H "Content-Type: application/json" -d '{"session_id":"s_xxx"}'
curl http://localhost:8000/api/report/s_xxx

# 6. 重启验证：重启 uvicorn 后再次 curl /api/report/s_xxx 仍能返回数据
```
