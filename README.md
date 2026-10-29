# 智能教育机器人 — 大数据构建（后端）

本目录是「智能教育机器人项目」的**大数据构建分析负责人**代码，运行在树莓派上，
对外提供会话、语音回合、人脸特征、画像报告的 FastAPI 服务。

## 快速启动

```bash
# 1. 安装依赖（首次）
pip install fastapi uvicorn python-multipart httpx

# 2. 启动（Mock 模式，默认，无需 AI 密钥）
MOCK_AI=1 python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell 下启动：`$env:MOCK_AI="1"; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`

接入真实 AI 时：设置环境变量后关闭 Mock。

```bash
MOCK_AI=0 ASR_API_KEY=... LLM_API_KEY=... LLM_BASE_URL=... LLM_MODEL=... TTS_API_KEY=... \
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> 密钥只从环境变量读取，代码中不出现任何密钥明文。树莓派建议单 worker。

## 目录结构

```
app/
  main.py                 # FastAPI 入口与路由注册（数据负责人统一维护）
  routers/
    ingest.py             # session start/end、focus、report
    turn.py               # /api/turn 语音回合
  services/
    db.py                 # SQLite 建表与访问（字段可迁移 PostgreSQL）
    asr.py                # ASR 适配（Mock/真实）
    llm.py                # LLM 适配（Mock/真实）
    tts.py                # TTS 适配（Mock/真实）
    analytics.py          # 清洗、时间窗平滑、参与度、画像报告
    errors.py             # 统一错误码
  data/app.db             # SQLite 数据文件（运行时生成）
  static/audio/           # Mock TTS 音频
docs/data-contract.md     # 数据契约（接口唯一依据，三方共享）
scripts/
  smoke_test.py           # 端到端冒烟测试（验收标准自动化）
  gen_mock_audio.py       # 生成 Mock 音频
```

## 接口一览

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | /api/health | 服务与数据库状态 |
| POST | /api/session/start | 创建会话，返回 session_id |
| POST | /api/turn | 上传音频，返回 transcript/reply/audio_url |
| POST | /api/focus | 保存单条人脸特征 |
| POST | /api/session/end | 结束会话并生成画像 |
| GET | /api/report/{id} | 对话画像与专注度综合报告 |

详细字段与错误码见 `docs/data-contract.md`。

## 验收验证

```bash
python scripts/smoke_test.py            # 全流程：3 段音频 + 20 条特征 → 报告
```

通过条件（data-contract.md 第 5 节）：
- 连续上传 3 段音频返回多轮回复与 TTS 地址
- 上传 20 条特征后报告输出有效特征数与参与度曲线
- 结束会话返回画像；服务重启后 `/api/report/{id}` 仍可查询

## 演示数据

- Mock 回复 5 组预置问答（asr.py / llm.py）
- Mock 音频：1 kHz 占位正弦波，证明音频链路可用；演示前替换为真实 TTS 输出
- 人脸特征分析：quality<0.5 与非法枚举剔除；60 秒时间窗平滑出参与度曲线
