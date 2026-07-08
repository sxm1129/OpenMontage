# DolphinLitePark 多模态与大语言模型集成调用指南 (V3)

> **更新日志**：
> - V3.1（2026-07-08）— 新增 `Wan2.2`（H100 自建集群，文生视频/图生视频）；修正 IndexTTS / Flux2 / LTX 2.3 的 `model` 标识（H100 模型公开命名已从 `h100/*` 迁移为 `leapfast/*`，本指南此前一直是旧名，按旧文档调用会 404，本次已全部更正）。
> - V3（2026-06-28）— IndexTTS 升级 V3 情绪参数、修正异步流程；Flux2 修正异步架构并新增图生图（I2I）；LTX 2.3 完善帧数/分辨率约束与 I2V 三种传图方式。

本指南旨在帮助您在其他项目中快速集成并调用 DolphinLitePark 的模型，包括 `IndexTTS`、`Flux2`、`LTX 2.3`、`Wan2.2`、`HappyHorse`、`Seedance 2.0`、`NanoBanana` 以及 `DeepSeek-V4-Pro`。

---

## 0. 基础认证与网关地址

- **MaaS 网关基础地址**: `https://api.aiapbot.com`
- **鉴权 Header**: `Authorization: Bearer sk-dlp-REDACTED-see-.env-MAAS_API_KEY`
- **Content-Type**: `application/json`

---

## 1. IndexTTS — 语音合成 (TTS)

IndexTTS 是基于自建 H100 GPU 集群的中文语音合成模型，采用**异步作业**模式：提交后返回 `job_id`，需轮询状态、再下载 WAV 音频。典型延迟 2–15 秒，2 个 GPU Worker 并发。

- **模型标识 (model)**: `leapfast/indextts`
- **请求端点**: `POST https://api.aiapbot.com/v1/audio/speech`

### 1.1 调用流程

```
① POST /v1/audio/speech           → 提交任务，返回 { id, status: "processing" }
② GET  /v1/audio/jobs/{id}        → 轮询状态，直到 status = "succeeded"
③ GET  /v1/audio/jobs/{id}/result → 下载 WAV 音频流
```

### 1.2 请求参数

#### 基础参数

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :---: | :---: | :---: | :--- |
| `model` | String | 是 | — | `leapfast/indextts` |
| `input` | String | 是 | — | 待合成文本（支持中英文混读，建议 ≤ 500 字） |
| `voice` | String | 否 | `zh_female_gossip` | 音色 ID，见下方音色列表 |

#### V3 情绪与停顿参数

| 参数名 | 类型 | 默认值 | 取值范围 | 描述 |
| :--- | :---: | :---: | :---: | :--- |
| `emo_alpha` | Float | `1.0` | `0.0 ~ 1.0` | 情绪强度。`0.0` = 情绪最弱（平淡），`1.0` = 最强。**`0.0` 是有效值，会被正确透传** |
| `use_emo_text` | Boolean | `false` | `true/false` | 是否启用情绪引导文本 |
| `emo_text` | String | — | 自由文本 | 情绪描述词，如 `"happy"` `"sad"` `"whispering"`。`use_emo_text=true` 时生效 |
| `interval_silence` | Integer | `200` | `0 ~ 2000`（ms） | 句间停顿时长（毫秒） |

### 1.3 预置音色

| voice_id | 描述 | OpenAI 等效 |
| :--- | :--- | :--- |
| `zh_female_intellectual` | 知性女声 | `alloy` |
| `zh_male_broadcaster` | 播音男声 | `echo` |
| `zh_female_youthful` | 青春女声 | `fable` |
| `zh_male_deep` | 浑厚男声 | `onyx` |
| `zh_female_warm` | 温柔女声 | `nova` |
| `zh_female_soothing` | 舒缓女声 | `shimmer` |
| `zh_female_gossip` | 亲切女声（**默认**） | — |

> 通过 `GET /v1/audio/voices/provider-list?provider_code=h100_cluster` 可获取完整动态音色列表。

### 1.4 cURL 调用示例

```bash
API_KEY="sk-dlp-REDACTED-see-.env-MAAS_API_KEY"

# ① 提交合成任务
JOB=$(curl -s -X POST "https://api.aiapbot.com/v1/audio/speech" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "leapfast/indextts",
    "input": "欢迎使用 DolphinLitePark 语音合成服务，今天天气真好！",
    "voice": "zh_female_intellectual"
  }')

JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Job ID: $JOB_ID"

# ② 轮询状态
while true; do
  STATUS=$(curl -s "https://api.aiapbot.com/v1/audio/jobs/$JOB_ID" \
    -H "Authorization: Bearer $API_KEY" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "succeeded" ] && break
  [ "$STATUS" = "failed" ] && echo "Failed!" && exit 1
  sleep 2
done

# ③ 下载 WAV 音频
curl -s "https://api.aiapbot.com/v1/audio/jobs/$JOB_ID/result" \
  -H "Authorization: Bearer $API_KEY" \
  -o output.wav

echo "Audio saved to output.wav"
```

### 1.5 情绪参数示例（V3 新增）

```bash
# 高情绪强度 + 引导词（兴奋风格）
curl -s -X POST "https://api.aiapbot.com/v1/audio/speech" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "leapfast/indextts",
    "input": "太棒了！我们成功了！",
    "voice": "zh_female_intellectual",
    "emo_alpha": 1.0,
    "use_emo_text": true,
    "emo_text": "excited"
  }'

# 平淡朗读（新闻播报风）
curl -s -X POST "https://api.aiapbot.com/v1/audio/speech" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "leapfast/indextts",
    "input": "今日沪深两市高开低走，成交量较昨日有所萎缩。",
    "voice": "zh_male_broadcaster",
    "emo_alpha": 0.0,
    "interval_silence": 400
  }'
```

### 1.6 Python 完整示例

```python
import time, requests

API_KEY = "sk-dlp-REDACTED-see-.env-MAAS_API_KEY"
BASE = "https://api.aiapbot.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def synthesize(text: str, voice: str = "zh_female_intellectual", **kwargs) -> bytes:
    # ① 提交
    resp = requests.post(f"{BASE}/audio/speech", headers=HEADERS, json={
        "model": "leapfast/indextts",
        "input": text,
        "voice": voice,
        **kwargs,  # emo_alpha, use_emo_text, emo_text, interval_silence
    })
    resp.raise_for_status()
    job_id = resp.json()["id"]
    print(f"Job submitted: {job_id}")

    # ② 轮询
    while True:
        r = requests.get(f"{BASE}/audio/jobs/{job_id}", headers=HEADERS)
        r.raise_for_status()
        status = r.json()["status"]
        print(f"  status: {status}")
        if status == "succeeded":
            break
        if status == "failed":
            raise RuntimeError("IndexTTS job failed")
        time.sleep(2)

    # ③ 下载
    audio = requests.get(f"{BASE}/audio/jobs/{job_id}/result", headers=HEADERS)
    audio.raise_for_status()
    return audio.content  # WAV bytes


# 基础合成
wav = synthesize("欢迎使用语音合成服务！")
with open("output.wav", "wb") as f:
    f.write(wav)

# 情绪控制（V3）
wav2 = synthesize(
    "这真是太令人激动了！",
    voice="zh_female_intellectual",
    emo_alpha=0.9,
    use_emo_text=True,
    emo_text="excited",
    interval_silence=300,
)
with open("output_emo.wav", "wb") as f:
    f.write(wav2)
```

### 1.7 返回示例

**① 提交响应**
```json
{ "id": "tts-a1b2c3d4", "status": "processing" }
```

**② 轮询响应**
```json
{ "status": "succeeded", "job_id": "tts-a1b2c3d4" }
```

**③ 音频结果**：直接返回 WAV 音频流（`Content-Type: audio/wav`）。

---

## 2. Flux2 — 图像生成（文生图 / 图生图）

Flux2 是基于自建 H100 GPU 集群的图像生成模型，采用**异步作业**模式：提交后返回 `job_id`，需轮询状态、再获取图片 URL。典型延迟 30–60 秒（1024×576），2 个 GPU Worker 并发。

- **模型标识 (model)**: `leapfast/flux2`
- **请求端点**: `POST https://api.aiapbot.com/v1/images/generations`
- **输出格式**: PNG（通过网关本地缓存 URL 访问，有效期 7 天）

### 2.1 调用流程

```
① POST /v1/images/generations        → 提交任务，返回 { id, status: "processing" }
② GET  /v1/images/jobs/{id}          → 轮询状态，直到 status = "succeeded"
③ GET  /v1/images/jobs/{id}/result   → 获取结果（JSON 含图片 URL）
```

### 2.2 请求参数

#### 通用参数（文生图 / 图生图共用）

| 参数名 | 类型 | 必填 | 默认值 | 取值范围 | 描述 |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `model` | String | 是 | — | — | `leapfast/flux2` |
| `prompt` | String | 是 | — | — | 图像描述提示词，支持中英文 |
| `width` | Integer | 否 | `1360` | 256–2048 | 输出宽度，建议使用 64 的倍数 |
| `height` | Integer | 否 | `768` | 256–2048 | 输出高度，建议使用 64 的倍数 |
| `num_steps` | Integer | 否 | `50` | 1–100 | 扩散步数，越高细节越丰富，耗时增加 |
| `guidance` | Float | 否 | `4.0` | 0–20 | 提示词引导强度（`0.0` 为有效值） |
| `seed` | Integer | 否 | 随机 | ≥0 | 随机种子，相同 seed + prompt 可复现结果（`0` 为有效值） |
| `model_name` | String | 否 | `flux.2-klein-base-9b` | — | 底层模型变体 |

#### 图生图专属参数

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :---: | :---: | :--- |
| `input_image` | String | 是 | 参考图 base64，格式：`data:image/png;base64,...` 或原始 base64 字符串。**目前仅支持 base64，不支持 URL** |

### 2.3 文生图（T2I）示例

```bash
API_KEY="sk-dlp-REDACTED-see-.env-MAAS_API_KEY"

# ① 提交
JOB=$(curl -s -X POST "https://api.aiapbot.com/v1/images/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "leapfast/flux2",
    "prompt": "A red apple on a clean white desk, studio lighting, photorealistic",
    "width": 1024,
    "height": 576,
    "num_steps": 30,
    "guidance": 4.0
  }')

JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Job ID: $JOB_ID"

# ② 轮询
while true; do
  STATUS=$(curl -s "https://api.aiapbot.com/v1/images/jobs/$JOB_ID" \
    -H "Authorization: Bearer $API_KEY" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "succeeded" ] && break
  [ "$STATUS" = "failed" ] && echo "Failed!" && exit 1
  sleep 5
done

# ③ 获取结果
curl -s "https://api.aiapbot.com/v1/images/jobs/$JOB_ID/result" \
  -H "Authorization: Bearer $API_KEY"
```

### 2.4 图生图（I2I）示例

将参考图编码为 base64，通过 `input_image` 字段传入：

```bash
# 将参考图转为 base64 data URI
IMG_B64="data:image/png;base64,$(base64 -w0 reference.png)"   # Linux; macOS 去掉 -w0

# ① 提交图生图任务
JOB=$(curl -s -X POST "https://api.aiapbot.com/v1/images/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"leapfast/flux2\",
    \"prompt\": \"把图中的苹果改成卡通风格，色彩鲜艳\",
    \"input_image\": \"${IMG_B64}\",
    \"width\": 1024,
    \"height\": 576,
    \"num_steps\": 30
  }")

JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "I2I Job ID: $JOB_ID"
# ② 轮询 + ③ 获取结果（同文生图）
```

### 2.5 Python 完整示例（T2I + I2I）

```python
import base64, time, requests

API_KEY = "sk-dlp-REDACTED-see-.env-MAAS_API_KEY"
BASE = "https://api.aiapbot.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def generate_image(payload: dict) -> str:
    """提交任务，轮询完成，返回图片 URL。"""
    # ① 提交
    resp = requests.post(f"{BASE}/images/generations", headers=HEADERS, json=payload)
    resp.raise_for_status()
    job_id = resp.json()["id"]
    print(f"Job submitted: {job_id}")

    # ② 轮询
    while True:
        r = requests.get(f"{BASE}/images/jobs/{job_id}", headers=HEADERS)
        r.raise_for_status()
        status = r.json()["status"]
        print(f"  status: {status}")
        if status == "succeeded":
            break
        if status == "failed":
            raise RuntimeError("Flux2 job failed")
        time.sleep(5)

    # ③ 获取结果
    result = requests.get(f"{BASE}/images/jobs/{job_id}/result", headers=HEADERS)
    result.raise_for_status()
    return result.json()["data"][0]["url"]


# ── 文生图 (T2I) ─────────────────────────────────────────────
url = generate_image({
    "model": "leapfast/flux2",
    "prompt": "A red apple on a white desk, studio lighting, photorealistic",
    "width": 1024,
    "height": 576,
    "num_steps": 30,
    "guidance": 4.0,
})
print("Image URL:", url)


# ── 图生图 (I2I) ─────────────────────────────────────────────
def load_image_b64(path: str) -> str:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = path.rsplit(".", 1)[-1].lower()
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
    return f"data:{mime};base64,{data}"


url_i2i = generate_image({
    "model": "leapfast/flux2",
    "prompt": "把图中的苹果改成卡通风格，色彩鲜艳",
    "input_image": load_image_b64("reference.png"),
    "width": 1024,
    "height": 576,
    "num_steps": 30,
})
print("I2I Image URL:", url_i2i)
```

### 2.6 返回示例

**① 提交响应**
```json
{ "id": "img-4bc45973", "status": "processing" }
```

**② 轮询响应**
```json
{ "status": "succeeded", "job_id": "img-4bc45973" }
```

**③ 结果响应**
```json
{
  "status": "succeeded",
  "data": [{ "url": "https://api.aiapbot.com/v1/images/assets/h100_flux_img-4bc45973.png" }],
  "job_id": "img-4bc45973"
}
```

### 2.7 典型尺寸参考

| 用途 | width | height | 参考耗时 |
| :--- | :---: | :---: | :--- |
| 横版 16:9（推荐） | 1024 | 576 | ~30–60s |
| 竖版 9:16 | 576 | 1024 | ~30–60s |
| 正方形 1:1 | 768 | 768 | ~30–60s |
| 宽屏（默认） | 1360 | 768 | ~45–90s |

---

## 3. LTX 2.3 — 文生视频与图生视频 (T2V / I2V)

LTX 2.3 是基于 H100 平台的高性能视频生成模型（Lightricks LTX-2.3 22B），采用**异步任务**架构。

- **模型标识 (model)**: `leapfast/ltx-2.3`
- **请求端点**: `POST https://api.aiapbot.com/v1/video/generations`

### 3.1 调用流程

```
① POST /v1/video/generations      → 提交任务，返回 { id, status: "processing" }
② GET  /v1/video/jobs/{id}        → 轮询状态（建议每 5s 一次）
   status: processing → 继续；succeeded → 可下载；failed → 查 error
③ GET  /v1/video/jobs/{id}/result → 下载 MP4 视频流
```

### 3.2 请求参数

#### 基础参数

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :---: | :---: | :---: | :--- |
| `model` | String | 是 | — | `leapfast/ltx-2.3` |
| `prompt` | String | 是 | — | 视频描述提示词（英文效果更佳） |
| `duration` | Float | 否 | — | 目标时长（秒），系统自动对齐到合法帧数 |
| `resolution` | String | 否 | `720P` | 快捷分辨率：`480P` / `720P` / `1080P`（与 width/height 互斥） |
| `width` | Integer | 否 | 1536 | 宽度，**必须是 64 的倍数** |
| `height` | Integer | 否 | 1024 | 高度，**必须是 64 的倍数**。注：1080p 须用 `1088`，非 `1080` |
| `seed` | Integer | 否 | 随机 | 固定种子可复现结果 |

#### Pipeline 与质量参数

| 参数名 | 类型 | 默认值 | 描述 |
| :--- | :---: | :---: | :--- |
| `pipeline` | String | `distilled` | `distilled`（快速，生产默认）或 `two_stage`（高质量） |
| `num_frames` | Integer | 121 | 帧数，未传 `duration` 时生效；须满足 `(num_frames - 1) % 8 == 0`，范围 9–721 |
| `frame_rate` | Float | 24.0 | 帧率 |
| `num_inference_steps` | Integer | 30 | 去噪步数，仅 `two_stage` 模式生效 |
| `negative_prompt` | String | 内置 | 负向提示，仅 `two_stage` |
| `enhance_prompt` | Boolean | false | 自动 LLM 增强 prompt 描述 |

#### 图生视频（I2V）参数

| 参数名 | 类型 | 默认值 | 描述 |
| :--- | :---: | :---: | :--- |
| `image` | String | — | **首选**：参考首帧，`data:image/...;base64,...` 格式或纯 base64 字符串 |
| `image_url` | String | — | 参考首帧公网 URL（`https://`） |
| `image_base64` | String | — | 显式 base64 字段，优先级高于 `image` |
| `image_strength` | Float | `0.8` | 参考图锁定强度 `0~1`；`0` 忽略参考图，`1` 强锁首帧，推荐 `0.8 ~ 0.9` |
| `image_frame_idx` | Integer | `0` | 参考图作用帧索引，默认 `0`（首帧） |

> **优先级**：`image_base64` > `image` > `image_url`，三者互斥，同时传入会报 422。

### 3.3 重要限制

- **宽高**：`width` / `height` 必须是 **64 的倍数**。1080p 须填 `1920×1088`（非 `1920×1080`）
- **帧数**：`num_frames` 须满足 `(num_frames - 1) % 8 == 0`，有效范围 9–721。传 `duration` 时系统自动对齐
- **最长时长**：30 秒（`duration: 30`）
- I2V 的三个图片字段互斥，任选其一传入

### 3.4 时长 ↔ 帧数对照（frame_rate=24）

| duration（秒） | num_frames | 实际时长 |
| :---: | :---: | :---: |
| 5 | 121 | ~5.04s |
| 10 | 241 | ~10.04s |
| 15 | 361 | ~15.04s |
| 20 | 481 | ~20.04s |
| 30 | 721 | ~30.04s |

### 3.5 Pipeline 选择

| pipeline | 速度 | 质量 | 适用场景 |
| :--- | :---: | :---: | :--- |
| `distilled` | 快（~5–90s） | 良好 | 生产默认、批量任务 |
| `two_stage` | 慢（~2–5 分钟） | 更高 | 最终输出、精调效果 |

### 3.6 文生视频（T2V）示例

```bash
API_KEY="sk-dlp-REDACTED-see-.env-MAAS_API_KEY"

# ① 提交
JOB=$(curl -s -X POST "https://api.aiapbot.com/v1/video/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "leapfast/ltx-2.3",
    "prompt": "A golden retriever playing on the beach at sunset, cinematic",
    "duration": 5,
    "width": 768,
    "height": 512,
    "pipeline": "distilled"
  }')

JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Job ID: $JOB_ID"

# ② 轮询
while true; do
  STATUS=$(curl -s "https://api.aiapbot.com/v1/video/jobs/$JOB_ID" \
    -H "Authorization: Bearer $API_KEY" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "succeeded" ] && break
  [ "$STATUS" = "failed" ] && echo "Failed!" && exit 1
  sleep 5
done

# ③ 下载
curl -s "https://api.aiapbot.com/v1/video/jobs/$JOB_ID/result" \
  -H "Authorization: Bearer $API_KEY" \
  -o ltx_output.mp4

echo "Saved to ltx_output.mp4"
```

### 3.7 图生视频（I2V）示例

**方式一：公网图片 URL**

```bash
curl -s -X POST "https://api.aiapbot.com/v1/video/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "leapfast/ltx-2.3",
    "prompt": "The cat gently turns its head and blinks, soft natural lighting",
    "image_url": "https://example.com/cat.jpg",
    "duration": 5,
    "width": 768,
    "height": 512,
    "image_strength": 0.85,
    "image_frame_idx": 0
  }'
```

**方式二：Base64 图片（推荐，无需公网图床）**

```bash
B64=$(base64 -w0 first_frame.jpg)   # Linux; macOS 去掉 -w0

curl -s -X POST "https://api.aiapbot.com/v1/video/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"leapfast/ltx-2.3\",
    \"prompt\": \"The woman turns to camera and smiles warmly, natural motion\",
    \"image\": \"data:image/jpeg;base64,${B64}\",
    \"duration\": 5,
    \"width\": 768,
    \"height\": 512,
    \"image_strength\": 0.85
  }"
```

### 3.8 Python 完整示例（T2V + I2V）

```python
import base64, time, requests
from pathlib import Path

API_KEY = "sk-dlp-REDACTED-see-.env-MAAS_API_KEY"
BASE    = "https://api.aiapbot.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def submit(payload: dict) -> str:
    resp = requests.post(f"{BASE}/video/generations", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()["id"]


def wait(job_id: str, interval: float = 5.0, timeout: float = 600.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{BASE}/video/jobs/{job_id}", headers=HEADERS)
        r.raise_for_status()
        status = r.json().get("status", "")
        print(f"  [{job_id}] status: {status}")
        if status in ("succeeded", "success", "completed"):
            return
        if status in ("failed", "error"):
            raise RuntimeError(f"Job {job_id} failed")
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} timed out")


def download(job_id: str, out_path: str) -> None:
    r = requests.get(f"{BASE}/video/jobs/{job_id}/result", headers=HEADERS)
    r.raise_for_status()
    Path(out_path).write_bytes(r.content)
    print(f"Saved: {out_path}")


# ── 文生视频 (T2V) ────────────────────────────────────────────
job = submit({
    "model": "leapfast/ltx-2.3",
    "prompt": "A cat walking on green grass, golden hour, cinematic",
    "duration": 5, "width": 768, "height": 512,
    "pipeline": "distilled",
})
wait(job)
download(job, "ltx_t2v.mp4")


# ── 图生视频 (I2V) — Base64 方式 ──────────────────────────────
def submit_i2v(prompt: str, image_path: str, strength: float = 0.85) -> str:
    raw  = Path(image_path).read_bytes()
    mime = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    b64  = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    return submit({
        "model": "leapfast/ltx-2.3",
        "prompt": prompt,
        "image": b64,
        "duration": 5, "width": 768, "height": 512,
        "image_strength": strength,
        "image_frame_idx": 0,
    })

# job_i2v = submit_i2v("The person smiles at camera, warm natural light", "ref.jpg")
# wait(job_i2v)
# download(job_i2v, "ltx_i2v.mp4")
```

### 3.9 返回与耗时参考

**提交响应**
```json
{ "id": "vid-c71d30bea172", "status": "processing" }
```

| 分辨率 / 时长 | 典型耗时 |
| :--- | :---: |
| 768×512，5s，distilled | 60–120 s |
| 768×512，10s，distilled | 120–240 s |
| 1920×1088，15s，two_stage | 2–5 分钟 |

建议轮询间隔 5–10 秒；冷启动首条额外 +60–90s。

---

## 4. Wan2.2 (TI2V-5B) — 文生视频与图生视频 (T2V / I2V)

Wan2.2 是基于 H100 平台的轻量级视频生成模型（Wan2.2-TI2V-5B），与 LTX 2.3 同属 H100 自建集群，但更轻、更快，适合 720p 级短视频与快速预览。**无音轨**（需要有声视频请用 LTX 2.3）。采用**异步任务**架构，与 LTX 2.3 共用同一套提交/轮询/下载端点。

- **模型标识 (model)**: `leapfast/wan2.2`
- **请求端点**: `POST https://api.aiapbot.com/v1/video/generations`

### 4.1 调用流程

```
① POST /v1/video/generations      → 提交任务，返回 { id, status: "processing" }
② GET  /v1/video/jobs/{id}        → 轮询状态（建议每 5s 一次）
   status: processing → 继续；succeeded → 可下载；failed → 查 error
③ GET  /v1/video/jobs/{id}/result → 下载 MP4 视频流（无音轨）
```

### 4.2 请求参数

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :---: | :---: | :---: | :--- |
| `model` | String | 是 | — | `leapfast/wan2.2` |
| `prompt` | String | 是 | — | 视频描述提示词（英文效果更佳） |
| `size` | String | 否 | `1280*704` | 仅支持 `1280*704`（横屏）或 `704*1280`（竖屏）；不传时会按 `width`/`height` 的比例自动判断横竖，两者都没有则默认横屏 |
| `duration` | Float | 否 | — | 目标时长（秒）。系统按 24fps 自动换算为 `frame_num` 并对齐到最近的合法帧数；显式传 `frame_num` 时本字段被忽略 |
| `frame_num` | Integer | 否 | `121`（H100 侧默认，约 5s） | 帧数，**须满足 `4n+1`**（如 5、17、81、121、241）。原生字段，显式传入时优先级最高，不做任何换算或校验，直接透传 |
| `seed` | Integer | 否 | 随机 | 固定种子可复现结果 |
| `sample_steps` | Integer | 否 | `50` | 扩散采样步数 1–100。也可用跨模型统一别名 `num_inference_steps`（`sample_steps` 未传时生效） |
| `sample_shift` | Float | 否 | 模型默认 | shift 参数，原生透传 |
| `sample_guide_scale` | Float | 否 | 模型默认 | CFG / guidance scale。也可用跨模型统一别名 `guidance`（`sample_guide_scale` 未传时生效） |
| `sample_solver` | String | 否 | `unipc` | `unipc` 或 `dpm++` |

#### 图生视频（I2V）参数

传入以下任一图片字段即触发 i2v（首帧条件生成），不传则为 t2v：

| 参数名 | 类型 | 描述 |
| :--- | :---: | :--- |
| `image` | String | **首选**：参考首帧，`data:image/...;base64,...` 格式或纯 base64 字符串 |
| `image_url` | String | 参考首帧公网 URL（`https://`） |
| `image_base64` | String | 显式 base64 字段，优先级高于 `image` |

> **优先级**：`image_base64` > `image` > `image_url`，三者互斥，同时传入以最高优先级为准。参考图大小上限 **20MB**。

### 4.3 重要限制

- **size**：仅两档，`1280*704` 或 `704*1280`，不支持任意宽高
- **frame_num**：须满足 `4n+1`；不合法会被上游 H100 拒绝（422）
- **无音频**：Wan2.2 输出的 MP4 不含音轨
- **并发**：H100 侧 Wan2.2 仅 **1 路 GPU 并行**，同一时刻只有一个任务在推理，其余排队（比 LTX 的 4 路并行更容易排队，批量调用请预留更长等待时间）

### 4.4 文生视频（T2V）示例

```bash
API_KEY="sk-dlp-REDACTED-see-.env-MAAS_API_KEY"

# ① 提交
JOB=$(curl -s -X POST "https://api.aiapbot.com/v1/video/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "leapfast/wan2.2",
    "prompt": "A golden retriever running on a sunny beach, cinematic lighting",
    "size": "1280*704",
    "frame_num": 17,
    "sample_steps": 20,
    "seed": 42
  }')

JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Job ID: $JOB_ID"

# ② 轮询
while true; do
  STATUS=$(curl -s "https://api.aiapbot.com/v1/video/jobs/$JOB_ID" \
    -H "Authorization: Bearer $API_KEY" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "succeeded" ] && break
  [ "$STATUS" = "failed" ] && echo "Failed!" && exit 1
  sleep 5
done

# ③ 下载
curl -s "https://api.aiapbot.com/v1/video/jobs/$JOB_ID/result" \
  -H "Authorization: Bearer $API_KEY" \
  -o wan_t2v_output.mp4

echo "Saved to wan_t2v_output.mp4"
```

### 4.5 图生视频（I2V）示例

**方式一：公网图片 URL**

```bash
curl -s -X POST "https://api.aiapbot.com/v1/video/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "leapfast/wan2.2",
    "prompt": "The man slowly turns his head and smiles warmly at the camera",
    "image_url": "https://example.com/portrait.jpg",
    "size": "704*1280",
    "frame_num": 17,
    "sample_steps": 20,
    "seed": 7
  }'
```

**方式二：Base64 图片（推荐，无需公网图床）**

```bash
B64=$(base64 -w0 portrait.jpg)   # Linux; macOS 去掉 -w0

curl -s -X POST "https://api.aiapbot.com/v1/video/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"leapfast/wan2.2\",
    \"prompt\": \"The man slowly turns his head and smiles warmly at the camera\",
    \"image\": \"data:image/jpeg;base64,${B64}\",
    \"size\": \"704*1280\",
    \"frame_num\": 17,
    \"sample_steps\": 20,
    \"seed\": 7
  }"
```

### 4.6 Python 完整示例（T2V + I2V + duration 自动换算）

```python
import base64, time, requests
from pathlib import Path

API_KEY = "sk-dlp-REDACTED-see-.env-MAAS_API_KEY"
BASE    = "https://api.aiapbot.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def submit(payload: dict) -> str:
    resp = requests.post(f"{BASE}/video/generations", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()["id"]


def wait(job_id: str, interval: float = 5.0, timeout: float = 300.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{BASE}/video/jobs/{job_id}", headers=HEADERS)
        r.raise_for_status()
        status = r.json().get("status", "")
        print(f"  [{job_id}] status: {status}")
        if status in ("succeeded", "success", "completed"):
            return
        if status in ("failed", "error"):
            raise RuntimeError(f"Job {job_id} failed")
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} timed out")


def download(job_id: str, out_path: str) -> None:
    r = requests.get(f"{BASE}/video/jobs/{job_id}/result", headers=HEADERS)
    r.raise_for_status()
    Path(out_path).write_bytes(r.content)
    print(f"Saved: {out_path}")


# ── 文生视频 (T2V) — 显式 frame_num ───────────────────────────
job = submit({
    "model": "leapfast/wan2.2",
    "prompt": "A cat walking on green grass, golden hour, cinematic",
    "size": "1280*704", "frame_num": 17, "sample_steps": 20, "seed": 42,
})
wait(job)
download(job, "wan_t2v.mp4")


# ── 文生视频 (T2V) — 用 duration 代替 frame_num（自动按 24fps 换算）──
job2 = submit({
    "model": "leapfast/wan2.2",
    "prompt": "Ocean waves gently rolling at sunset",
    "duration": 5,  # 自动换算为 frame_num=121（H100 默认 sample_steps=50，耗时约 3–5 分钟）
})
wait(job2, timeout=600.0)
download(job2, "wan_duration.mp4")


# ── 图生视频 (I2V) — Base64 方式 ──────────────────────────────
def submit_i2v(prompt: str, image_path: str, size: str = "1280*704") -> str:
    raw  = Path(image_path).read_bytes()
    mime = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    b64  = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    return submit({
        "model": "leapfast/wan2.2",
        "prompt": prompt,
        "image": b64,
        "size": size, "frame_num": 17, "sample_steps": 20,
    })

# job_i2v = submit_i2v("The person smiles at camera, warm natural light", "ref.jpg", size="704*1280")
# wait(job_i2v)
# download(job_i2v, "wan_i2v.mp4")
```

### 4.7 返回与耗时参考

**提交响应**
```json
{ "id": "vid-5f92eafe-a32e-459f-9fe3-2f6eb6132612", "status": "processing" }
```

| 参数 | 典型耗时（实测） |
| :--- | :---: |
| 17 帧，20 步（T2V / I2V） | ~10 s（热启动） |
| 121 帧，50 步（默认档，即 `duration: 5`） | ~3 分钟 |
| 冷启动首条 | 额外 +30–60 s（模型加载） |

建议轮询间隔 5–10 秒。仅 1 路 GPU 并行，排队中的任务 `status` 会保持 `processing` 直至轮到执行。

---

## 5. HappyHorse 1.0 — 阿里百炼视频模型

HappyHorse 是阿里百炼的高端视频生成系列模型，支持标准模式（平坦结构参数）和原生透传模式。

- **模型标识 (model)**:
  - 标准模式: `happyhorse-1.0-t2v`（文生视频）、`happyhorse-1.0-i2v`（图生视频）、`happyhorse-1.0-r2v`（参考图生）、`happyhorse-1.0-video-edit`（视频编辑）
  - 原生透传模式: 前缀增加 `native/`，如 `native/happyhorse-1.0-i2v`
- **请求端点**: `POST https://api.aiapbot.com/v1/video/generations`

### 请求参数（标准 DTO 模式）

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :---: | :---: | :---: | :--- |
| `model` | String | 是 | — | 例如 `happyhorse-1.0-i2v` |
| `prompt` | String | 是 | — | 画面运动描述 |
| `image` | String | 是（I2V） | — | 首帧参考图 URL，分辨率须至少 **300×300** 像素 |
| `duration_seconds` | Integer | 否 | `5` | 生成时长，百炼官方限制 5–15 秒 |
| `resolution` | String | 否 | `720P` | `720P` 或 `1080P` |

### cURL 调用示例（标准 DTO 图生视频）

```bash
curl -X POST https://api.aiapbot.com/v1/video/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-dlp-REDACTED-see-.env-MAAS_API_KEY" \
  -d '{
    "model": "happyhorse-1.0-i2v",
    "prompt": "A massive majestic waterfall in a lush tropical jungle, photorealistic",
    "image": "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=500",
    "duration_seconds": 5,
    "resolution": "720P"
  }'
```

### cURL 调用示例（原生透传模式）

```bash
curl -X POST https://api.aiapbot.com/v1/video/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-dlp-REDACTED-see-.env-MAAS_API_KEY" \
  -H "X-DLP-Passthrough: true" \
  -d '{
    "model": "native/happyhorse-1.0-i2v",
    "input": {
      "prompt": "A majestic cinematic gold dragon soaring elegantly through soft pastel clouds",
      "media": [
        { "type": "first_frame", "url": "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=500" }
      ]
    },
    "parameters": {
      "resolution": "720P",
      "duration": 5,
      "generate_audio": false
    }
  }'
```

### 返回与轮询

提交成功返回 `job_id`（以 `vid-` 开头）：
- **状态查询**: `GET https://api.aiapbot.com/v1/video/jobs/{job_id}`
- **视频下载**: `GET https://api.aiapbot.com/v1/video/jobs/{job_id}/result`

---

## 6. Seedance 2.0 — 火山方舟视频大模型

字节跳动 Seedance 2.0，支持透传调用火山引擎原生参数规格。

- **模型标识**: `volcengine/doubao-seedance-2.0`（快速版：`volcengine/doubao-seedance-2.0-fast`）
- **原生透传模式**: `native/volcengine/doubao-seedance-2.0`
- **请求端点**: `POST https://api.aiapbot.com/v1/video/generations`

> ⚠️ **图生视频（I2V）不允许传 `duration` 参数**，否则触发火山 `InvalidParameter` 400 报错。文生视频（T2V）可正常携带。

### cURL 调用示例（原生图生视频）

```bash
curl -X POST https://api.aiapbot.com/v1/video/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-dlp-REDACTED-see-.env-MAAS_API_KEY" \
  -d '{
    "model": "native/volcengine/doubao-seedance-2.0",
    "content": [
      { "type": "text", "text": "A beautiful cute kitten sitting on the grass under golden sunset, cinematic lighting, 4k" },
      { "type": "image_url", "image_url": { "url": "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=500" } }
    ],
    "ratio": "16:9"
  }'
```

### 返回与轮询

- **状态查询**: `GET https://api.aiapbot.com/v1/video/jobs/{job_id}`
- **视频下载**: `GET https://api.aiapbot.com/v1/video/jobs/{job_id}/result`

---

## 7. NanoBanana — 极速图像生成

NanoBanana（底层为 Visionular 提供的极速生成通道）采用**异步任务**架构进行文生图/图生图。

- **模型标识**: `gemini-3.1-flash-image-preview`
- **请求端点**: `POST https://api.aiapbot.com/v1/images/generations`

### 请求参数

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :---: | :---: | :---: | :--- |
| `model` | String | 是 | — | `gemini-3.1-flash-image-preview` |
| `prompt` | String | 是 | — | 描述词 |
| `images` | Array[String] | 否 | — | **图生图专用**：输入参考图 URL 数组 |
| `size` | String | 否 | `16x9` | 分辨率比率，支持 `16x9`、`3x4`、`1x1` 等 |
| `quality` | String | 否 | `1K` | 规格：`1K` 或 `2K` |

### cURL 调用示例（文生图）

```bash
curl -X POST "https://api.aiapbot.com/v1/images/generations" \
  -H "Authorization: Bearer sk-dlp-REDACTED-see-.env-MAAS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3.1-flash-image-preview",
    "prompt": "A beautiful landscape, masterpiece",
    "size": "16x9",
    "quality": "1K"
  }'
```

### 轮询与结果

```bash
# 轮询状态（每 3–5s 一次）
curl "https://api.aiapbot.com/v1/images/jobs/{job_id}" \
  -H "Authorization: Bearer $API_KEY"
```

完成时响应：
```json
{
  "status": "succeeded",
  "data": [{ "url": "https://api.aiapbot.com/v1/images/assets/gemini_output_xxxxx.png" }],
  "job_id": "img_c1a3b8cd2e74"
}
```

---

## 8. DeepSeek-V4-Pro — 商业级语言对话模型

接口完全兼容 OpenAI Chat Completions 协议，支持流式 / 非流式输出。

- **模型标识**: `bailian/deepseek-v4-pro`
- **请求端点**: `POST https://api.aiapbot.com/v1/chat/completions`

### 请求参数

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :---: | :---: | :---: | :--- |
| `model` | String | 是 | — | `bailian/deepseek-v4-pro` |
| `messages` | Array | 是 | — | 对话上下文，格式：`[{"role": "user", "content": "内容"}]` |
| `stream` | Boolean | 否 | `false` | 是否开启 SSE 流式输出 |
| `temperature` | Number | 否 | `0.7` | 采样温度 |

### cURL 调用示例

```bash
curl -X POST https://api.aiapbot.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-dlp-REDACTED-see-.env-MAAS_API_KEY" \
  -d '{
    "model": "bailian/deepseek-v4-pro",
    "messages": [{"role": "user", "content": "请用一句话说出你的系统优势？"}],
    "stream": false
  }'
```

---

## 9. 异步任务通用轮询指南

所有异步生成任务（IndexTTS、Flux2、LTX 2.3、Wan2.2、HappyHorse、Seedance、NanoBanana）获得 `job_id` 后，按以下方式轮询：

### 9.1 轮询端点汇总

| 任务类型 | 状态轮询 | 结果下载 |
| :--- | :--- | :--- |
| **音频**（IndexTTS） | `GET /v1/audio/jobs/{id}` | `GET /v1/audio/jobs/{id}/result`（WAV 二进制流） |
| **图像**（Flux2、NanoBanana） | `GET /v1/images/jobs/{id}` | `GET /v1/images/jobs/{id}/result`（JSON 含 URL） |
| **视频**（LTX 2.3、Wan2.2、HappyHorse、Seedance） | `GET /v1/video/jobs/{id}` | `GET /v1/video/jobs/{id}/result`（MP4 二进制流） |

### 9.2 轮询策略建议

| 任务类型 | 推荐轮询间隔 | 最大等待 |
| :--- | :---: | :---: |
| IndexTTS | 2 s | 60 s |
| Flux2 | 5 s | 120 s |
| LTX 2.3（短视频） | 5–10 s | 300 s |
| LTX 2.3（长视频 / two_stage） | 10 s | 600 s |
| Wan2.2（17 帧默认档） | 5 s | 60 s |
| Wan2.2（81/121 帧） | 10 s | 300 s |
| HappyHorse / Seedance | 10 s | 600 s |

### 9.3 通用轮询函数（Python）

```python
import time, requests

def poll(base: str, job_type: str, job_id: str, api_key: str,
         interval: float = 5.0, timeout: float = 600.0) -> dict:
    """
    base      — 'https://api.aiapbot.com/v1'
    job_type  — 'audio' | 'images' | 'video'
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{base}/{job_type}/jobs/{job_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
        status = data.get("status", "")
        print(f"  [{job_id}] {status}")
        if status in ("succeeded", "success", "completed"):
            return data
        if status in ("failed", "error"):
            raise RuntimeError(f"Job {job_id} failed: {data}")
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} timed out after {timeout}s")
```

### 9.4 状态说明

| status | 含义 |
| :---: | :--- |
| `processing` / `queued` | 排队或生成中，继续轮询 |
| `succeeded` | 生成完成，可下载结果 |
| `failed` | 生成失败，预扣费用已自动退回 |
