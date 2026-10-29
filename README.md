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
# LLM 示例：DeepSeek（任选一家 OpenAI 兼容平台，见下表）
MOCK_AI=0 LLM_API_KEY=sk-xxx LLM_BASE_URL=https://api.deepseek.com LLM_MODEL=deepseek-chat \
  ASR_API_KEY=sk-xxx ASR_BASE_URL=https://api.openai.com/v1 ASR_MODEL=whisper-1 \
  TTS_API_KEY=sk-xxx TTS_BASE_URL=https://api.openai.com/v1 TTS_MODEL=tts-1 TTS_VOICE=alloy \
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### AI 环境变量一览

| 变量 | 用途 | 国内平台参考 |
|---|---|---|
| `MOCK_AI` | `1`=Mock（默认）`0`=真实 AI | — |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | 对话模型（OpenAI 兼容 chat/completions） | DeepSeek `https://api.deepseek.com`+`deepseek-chat`；智谱 `https://open.bigmodel.cn/api/paas/v4`+`glm-4-flash`（免费）；通义 `https://dashscope.aliyuncs.com/compatible-mode/v1`+`qwen-plus`；硅基流动 `https://api.siliconflow.cn/v1` |
| `ASR_API_KEY` / `ASR_BASE_URL` / `ASR_MODEL` | 语音识别（OpenAI 兼容 /audio/transcriptions） | OpenAI `whisper-1`；硅基流动/火山方舟同接口 |
| `TTS_API_KEY` / `TTS_BASE_URL` / `TTS_MODEL` / `TTS_VOICE` | 语音合成（OpenAI 兼容 /audio/speech） | OpenAI `tts-1`+`alloy`；硅基流动同接口 |

> 密钥只从环境变量读取，代码中不出现任何密钥明文。树莓派建议单 worker。

### 推荐：用 `.env` 文件管理密钥（项目启动时自动加载）

`.env` 放项目根目录（已被 `.gitignore` 排除，**不会也不应提交到仓库**）。
以下为**硅基流动**平台真实部署模板（本项目实测通过）：

```bash
# 模式：0=真实 AI，1=Mock（默认）
MOCK_AI=0

# 硅基流动 API Key（在 https://cloud.siliconflow.cn 创建，充值后可用）
LLM_API_KEY=sk-你的密钥
ASR_API_KEY=sk-你的密钥
TTS_API_KEY=sk-你的密钥

# 三家共用同一地址
LLM_BASE_URL=https://api.siliconflow.cn/v1
ASR_BASE_URL=https://api.siliconflow.cn/v1
TTS_BASE_URL=https://api.siliconflow.cn/v1

# 模型（硅基流动模型广场可查最新型号）
LLM_MODEL=deepseek-ai/DeepSeek-V4.1-Flash
ASR_MODEL=FunAudioLLM/SenseVoiceSmall
TTS_MODEL=FunAudioLLM/CosyVoice2-0.5B
# 音色格式必须是「模型:音色名」，例如 FunAudioLLM/CosyVoice2-0.5B:alex
TTS_VOICE=FunAudioLLM/CosyVoice2-0.5B:alex
```

> 注意：ASR/LLM/TTS 用**同一个 key** 即可（同一账户）。新注册用户通常有免费额度；
> 若接口返回 402/余额不足，去硅基流动充值即可，无需改代码。
> 密钥是敏感信息：不要发群里、不要提交仓库；同学各自注册自己的账户最安全。

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
  static/audio/           # Mock/真实 TTS 音频 + 演示测试语音 demo_*.wav
  static/verify.html      # 前端验证台（浏览器打开即可验证全链路）
docs/
  data-contract.md        # 数据契约（接口唯一依据，三方共享）
  素材/学生表情/           # 学生表情演示图片（表情→专注度讲解用）
scripts/
  smoke_test.py           # 端到端冒烟测试（验收标准自动化）
  gen_mock_audio.py       # 生成 Mock 音频
  test_real_ai.py         # 真实 AI 单测（LLM/ASR/TTS 三件套）
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

## 前端验证台（验证树莓派跑通用）

后端启动后，浏览器打开 **`http://<主机IP>:8000/static/verify.html`**（本机用 `127.0.0.1`）。

页面按 4 步走完即证明整条链路通：

1. **服务自检** — 确认后端在线、数据表已建
2. **创建会话 + 语音对话** — 上传一段音频 → 显示识别文字 + 机器人回答 + 可播放合成语音（真实模式下可连续多轮）
3. **模拟专注度特征** — 一键发送 20 条人脸特征（含缺席/低头/闭眼/低质量等异常项）
4. **结束会话 + 报告** — 生成对话画像 + 专注度曲线 + 综合建议

自带的演示测试语音（学生提问，可直接上传）：`app/static/audio/demo_q1_math.wav`（数学）、
`demo_q2_focus.wav`（专注力）、`demo_q3_science.wav`（科学）。

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
- 演示语音：`app/static/audio/demo_*.wav` 为童声学生提问（数学/专注力/科学），真实模式下可直接上传验证 ASR→LLM→TTS 全链路
- 演示图片：`docs/素材/学生表情/` 为教室场景学生表情（开心/微笑/举手/走神/思考），讲解"表情→专注度特征"概念时使用
