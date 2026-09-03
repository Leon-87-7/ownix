# Research: self-hosting `litert-community/gemma-4-E2B-it-litert-lm` on a VPS as vig's enrichment model

Date: 2026-09-03
Scope: pure research, no code changes. Answers whether a self-hosted LiteRT-LM + Gemma model on a generic (no-GPU) VPS could replace the Gemini API calls in `src/services/gemini.py`.

## Verdict

**Not a good drop-in replacement today, but it is a real and increasingly viable option for the text-only parts of vig's enrichment pipeline.** Three findings drive this:

1. The model name the user gave from memory turned out to be **exactly correct** — but for a reason nobody could have guessed from training data: Google shipped a **Gemma 4** generation (successor to Gemma 3n) between this assistant's knowledge cutoff and today, and `litert-community/gemma-4-E2B-it-litert-lm` is real, live, and actively maintained (1M+ downloads, 413 likes, `lastModified: 2026-08-31`). See §1.
2. LiteRT-LM is not mobile-only — it runs as a real Linux CLI/binary/Python library and, as of `v0.13`, ships a **first-party OpenAI-compatible HTTP server** (`litert-lm serve`) that vig could point an HTTP client at with almost no wrapper code. See §3.
3. The gap is **multimodal input through that server**: vig's actual Gemini usage (`call_gemini_vision`, `call_gemini_photo_links`, `select_informative_screenshots`) is 100% about sending multiple inline JPEG frames per call and getting back schema-constrained JSON. The documented `litert-lm serve` OpenAI surface only covers `/v1/models` and `/v1/chat/completions` with text and streaming — image input on that HTTP surface is undocumented. Vision/JSON-schema/tool-calling all exist in LiteRT-LM, but only via the CLI (`--attachment`) or the C++/Python APIs, not confirmed on the HTTP server. See §5–6.

Net: this is a strong candidate for a **cost-saving side channel for text-only enrichment** (article/repo/document paths in vig), not a safe wholesale replacement for the vision-heavy short-video/photo paths without writing a real wrapper service around the Python API (not just pointing at `litert-lm serve`).

---

## 1. What the model actually is

The user's exact string, `litert-community/gemma-4-E2B-it-litert-lm`, **is a real, current Hugging Face repo** — confirmed via the HF API (not a hallucination, not a typo of a Gemma 3n model):

```
id: litert-community/gemma-4-E2B-it-litert-lm
author: litert-community
base_model: google/gemma-4-E2B-it
license: apache-2.0
downloads: 1,035,115  |  likes: 413
lastModified: 2026-08-31
```
Source: [HF API model listing](https://huggingface.co/api/models/litert-community/gemma-4-E2B-it-litert-lm), [model card](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm)

**This is a discrepancy worth flagging explicitly against the task's own assumption**: the task brief guessed "E2B is likely a Gemma 3n variant." It is not — it is **Gemma 4**, a newer model family than Gemma 3n. The "E" = "effective parameters" naming convention (Per-Layer Embeddings keep the *effective* footprint far below the *total* parameter count) originated with Gemma 3n and was carried forward into Gemma 4's small models, per the base model card:

> "The 'E' in E2B and E4B stands for 'effective' parameters... Rather than adding more layers or parameters to the model, PLE gives each decoder layer its own small embedding for every token. These embedding tables are large but are only used for quick lookups, which is why the effective parameter count is much smaller than the total."
Source: [google/gemma-4-E2B-it model card](https://huggingface.co/google/gemma-4-E2B-it)

**Naming/suffix breakdown** (per the litert-community model card and HF metadata):
- `gemma-4` — the model family/generation.
- `E2B` — "effective 2B" parameters (2.3B effective, 5.1B including embeddings, per the Gemma 4 spec table).
- `it` — instruction-tuned variant (fine-tuned for chat/instructions), as opposed to the raw pretrained `google/gemma-4-E2B`.
- `litert-lm` — this checkpoint is packaged in the `.litertlm` container format for Google's LiteRT-LM runtime (as opposed to the `.task` MediaPipe format, also published in the same repo for the now-maintenance-mode MediaPipe path).

**License**: the repo tag is `apache-2.0`, and the base model's `license_link` points to `https://ai.google.dev/gemma/docs/gemma_4_license`. That page **is** the Apache 2.0 text, but Google gates Gemma usage behind an additional "Gemma Prohibited Use Policy" / intended-use terms referenced from the same page — so treat it as "Apache 2.0 plus Google's acceptable-use terms," not unrestricted Apache 2.0.
Source: [Gemma 4 license page](https://ai.google.dev/gemma/docs/gemma_4_license), [HF metadata for google/gemma-4-E2B-it](https://huggingface.co/api/models/google/gemma-4-E2B-it)

**Size / quantization** (from the `litert-community` model card, quoted verbatim):

> "LiteRT-LM uses a state of the art Gemma-4 mobile quantization scheme that uses a mixture of 2bit, 4bit and 8 bit weights. This means that for text only use cases the weight footprint in memory can be as low as 0.8 GB while the runtime uses memory mapping to support the 1.12GB of embedding parameters."

Disk file size (`.litertlm`) is **2,583 MB** for the general checkpoint, and a separate, text-only "web" variant is 2,008 MB. Source: [litert-community/gemma-4-E2B-it-litert-lm README](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm)

**Gemma 4 family context** (from the base `google/gemma-4-E2B-it` card): five sizes (E2B, E4B, 12B Unified, 26B A4B MoE, 31B Dense); E2B specifically has 35 layers, 512-token sliding window, **128K token context window** (native, pre-quantization — see the context-length discrepancy flagged in §5), 262K vocab, and supports Text + Image + Audio modalities with a ~150M-param vision encoder and ~300M-param audio encoder bolted onto the small models. Source: [google/gemma-4-E2B-it README](https://huggingface.co/google/gemma-4-E2B-it)

---

## 2. What LiteRT-LM actually is

LiteRT-LM is Google AI Edge's **on-device LLM inference orchestration layer**, built on top of LiteRT (the TensorFlow Lite successor):

> "LiteRT-LM is a specialized orchestration layer built directly on top of LiteRT, Google's high-performance multi-platform runtime trusted by millions of Android and edge developers. LiteRT provides the foundational hardware acceleration via XNNPack for CPU and ML Drift for GPU. LiteRT-LM adds the specialized GenAI libraries and APIs, such as KV-cache management, prompt templating, and function calling."
Source: [litert-community/gemma-4-E2B-it-litert-lm README](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm)

Official repo: [github.com/google-ai-edge/LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM). Official docs hub: [ai.google.dev/edge/litert-lm](https://ai.google.dev/edge/litert-lm) (canonical redirect target is `developers.google.com/edge/litert-lm/*`).

**Is it mobile/edge-only, or does it run on a generic Linux x86_64 VPS?** It genuinely supports desktop/server-class Linux, not just mobile:

- Supported platforms per the official overview: **Android, iOS, macOS, Windows, Linux, and IoT (e.g. Raspberry Pi)**. Hardware acceleration: CPU on all platforms (via XNNPACK), GPU on Android/iOS/macOS/Windows/Linux, NPU on Android and (experimentally) Windows. Source: [LiteRT-LM overview](https://developers.google.com/edge/litert-lm/overview)
- It ships as an installable CLI (`pip install litert-lm` / `uv tool install litert-lm` / `uvx litert-lm`) requiring only **Python 3.10+** — no mobile toolchain needed to run it on a server. Source: [LiteRT-LM CLI installation](https://developers.google.com/edge/litert-lm/cli/installation)
- It also builds from source for Linux via Bazel 7.6.1 + clang, producing native binaries; a v0.16 release note explicitly calls out an experimental "YNNPACK" CPU delegate for **linux arm64** builds specifically, implying the default XNNPACK CPU path already targets Linux (x86_64 included) as a first-class target. Source: [LiteRT-LM build-and-run guide](https://github.com/google-ai-edge/LiteRT-LM/blob/main/docs/getting-started/build-and-run.md), [LiteRT-LM README v0.16 notes](https://github.com/google-ai-edge/LiteRT-LM/blob/main/README.md)
- LiteRT-LM already powers **production, non-mobile deployments**: "LiteRT-LM powers on-device GenAI experiences in Chrome, Chromebook Plus, Pixel Watch, and more" — i.e. desktop-class as well as mobile. Source: [LiteRT-LM README](https://github.com/google-ai-edge/LiteRT-LM/blob/main/README.md)

Conclusion: LiteRT-LM's own docs never present a generic cloud Linux VPS as the primary target audience (all the headline benchmarks are phones/laptops/Raspberry Pi/Jetson), but Linux x86_64/CPU is an explicitly supported, non-experimental execution target — a VPS is well within scope, just outside the marketing spotlight.

---

## 3. Running it on a Linux VPS: CLI, GPU vs CPU, and the HTTP server question

**Install** (no build-from-source needed for the common path):
```bash
pip install --upgrade litert-lm      # or: uv tool install litert-lm / uvx litert-lm
```
Source: [LiteRT-LM CLI installation guide](https://developers.google.com/edge/litert-lm/cli/installation)

**Run a one-off prompt**, pulling the model straight from Hugging Face:
```bash
litert-lm run \
   --from-huggingface-repo=litert-community/gemma-4-E2B-it-litert-lm \
   gemma-4-E2B-it.litertlm \
   --backend=cpu \
   --prompt="What is the capital of France?"
```
(`--backend=gpu` is the alternative; on a GPU-less VPS `--backend=cpu` is the only viable path, and CPU execution goes through the XNNPACK delegate.) Source: [LiteRT-LM README](https://github.com/google-ai-edge/LiteRT-LM/blob/main/README.md)

**Does it expose an HTTP/OpenAI-compatible server out of the box?** Yes — as of release `v0.13`:

> `v0.13`: Support Gemma4 12B. Added Agent skill support for Android demo app, **OpenAI API compatible server in CLI**, and MacOS support in Swift package.
Source: [LiteRT-LM README releases list](https://github.com/google-ai-edge/LiteRT-LM/blob/main/README.md)

Concretely:
```bash
litert-lm serve --host 0.0.0.0 --port 9379   # both flags optional, these are the documented defaults
```
This exposes:
- `GET /v1/models` — lists models currently loaded in the local registry
- `POST /v1/chat/completions` — OpenAI-shaped chat completion request, **with streaming (SSE) support**

The server "dynamically loads and serves any models in your local registry," matching the OpenAI wire format for model name + message history. Source: [LiteRT-LM OpenAI-Compatible Server docs](https://developers.google.com/edge/litert-lm/cli/openai_server)

**What wrapping vig would still need to do:** the documented `/v1/chat/completions` surface only covers text chat + streaming. It does **not** document:
- image/vision content parts (no mention of multimodal message content in the OpenAI-server docs),
- a `response_format`/JSON-schema passthrough (structured output is documented only at the C++ `ConversationConfig`/LLGuidance level — see §5),
- function/tool-calling passthrough (tool calling in the CLI is done via a `preset.py` that the CLI process itself executes, not something an external HTTP caller supplies per-request the way OpenAI's `tools` param works).

So for vig's **text-only** enrichment calls (article/repo/document paths, which just call `generate(prompt, model=...)`), `litert-lm serve` could plausibly be called almost directly via an OpenAI-style HTTP client. For the **vision** calls (short-video frame analysis, photo OCR, screenshot selection — all of which pass `types.Part.from_bytes(...)` image parts to Gemini today), the safer, verified path is the **Python API** (`litert_lm.Engine` + `Conversation` + `Content.ImageFile()`/`AudioFile()`) embedded inside a small first-party FastAPI/Flask wrapper process, not the stock `serve` command, since image input on `serve` is unverified. Source: [LiteRT-LM Python API guide](https://developers.google.com/edge/litert-lm/python)

---

## 4. Hardware/resource requirements for E2B on CPU

The `litert-community/gemma-4-E2B-it-litert-lm` model card publishes first-party benchmarks (1024 prefill tokens / 256 decode tokens / 2048-token context window, XNNPACK CPU delegate with 4 threads, TTFT excludes model load time):

| Platform | Backend | Prefill (tok/s) | Decode (tok/s) | TTFT (s) | Disk size (MB) | CPU Memory (MB) |
|---|---|---|---|---|---|---|
| Linux, Arm 2.3–2.8GHz | CPU | 260 | 35.0 | 4.0 | 2583 | 1628 |
| Linux, NVIDIA RTX 4090 | GPU | 11,234 | 143.4 | 0.1 | 2583 | 913 |
| Windows, Intel Lunar Lake | CPU | 435 | 29.8 | 2.39 | 2583 | 3505 |
| macOS, MacBook Pro M4 Max | CPU | 901 | 41.6 | 1.1 | 2583 | 736 |
| Raspberry Pi 5 (16GB) | CPU | 133 | 7.6 | 7.8 | 2583 | 1546 |

Source: [litert-community/gemma-4-E2B-it-litert-lm README](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm) (full table also includes Android/iOS/Jetson/Web/NPU rows)

Takeaways for a **generic, GPU-less VPS**:
- **RAM**: budget roughly **1.5–3.5 GB** just for the model runtime at 2048-token context, on top of everything else vig's worker process needs (the model card's own "0.8GB weight footprint" figure is a best case for pure text-only weight residency and excludes the measured runtime overhead shown in the table above).
- **Disk**: ~2.5 GB per model checkpoint (2,583 MB `.litertlm` file).
- **Throughput/latency (CPU-only)**: expect roughly **30–40 decode tokens/sec** on a modern x86/ARM server core count similar to the Linux/Windows rows above, with a several-second time-to-first-token at 2048-token context. That is workable for vig's async, queue-based worker (`BRPOP`/Redis job model — latency of a few seconds to tens of seconds per enrichment call is already the norm with Gemini's own network round-trip), but it is **not** interactive-chat-fast, and a cheap/low-core-count VPS could land closer to the Raspberry Pi 5 row (7–12 tok/s) than the desktop rows.
- Context length used for these benchmarks was capped at 2048 tokens even though the readme separately states "the model can support up to 32k context length" for this checkpoint — see the discrepancy noted in §5.
- No official published number exists yet for vig's actual multi-frame vision workload (multiple 256-tokens-per-image inputs) on CPU-only Linux; the vision/audio encoders are noted as "loaded on demand" to control memory, but no CPU vision throughput benchmark row is published for Linux (only implied via the general model size number).

---

## 5. Feature gap vs. what `src/services/gemini.py` actually relies on

Reading `src/services/gemini.py` directly, vig's current Gemini usage needs, concretely:

1. **Strict JSON-schema-constrained output** — `_call_sync()` passes `response_mime_type="application/json"` + `response_schema=<pydantic-like schema>` to `google-genai`'s `GenerateContentConfig`, used by `select_informative_screenshots()` (array-of-objects schema) and implicitly relied on by the prompt-engineered JSON contracts in `_VISION_PROMPT`/`_PHOTO_PROMPT` for `call_gemini_vision()`/`call_gemini_photo_links()`.
2. **Multi-image vision input** — `call_gemini_vision()` and `call_gemini_photo_links()` both send a list of inline JPEG frames per single call (`types.Part.from_bytes(...)` repeated N times), not one image at a time.
3. **Plain text generation with schema** — `generate()` is used by article/repo/document processors, and by `select_informative_screenshots()`/`resolve_tool_urls()`.
4. All vision/photo calls pin `model="gemini-2.5-flash"`; there's no function-calling usage anywhere in `gemini.py` today.

Mapped against LiteRT-LM / Gemma 4 E2B capabilities:

| vig requirement | LiteRT-LM / Gemma 4 E2B support | Source |
|---|---|---|
| JSON-schema-constrained output | **Yes, but only confirmed at the C++ `ConversationConfig`/LLGuidance level** ("LLGuidance... Supports Regex, JSON Schema, and Lark grammars"). Not confirmed as exposed through the `litert-lm serve` HTTP surface or the Python API docs reviewed. | [Constrained decoding docs](https://github.com/google-ai-edge/LiteRT-LM/blob/main/docs/api/cpp/constrained-decoding.md) |
| Multi-image vision input | Model itself supports vision natively (Gemma 4 E2B: Text+Image+Audio, ~150M-param vision encoder). CLI supports `--attachment` (repeatable, so multiple images per call) with `--vision-backend=cpu\|gpu`. Python API exposes `litert_lm.Content.ImageFile()`/`Contents.of(...)` similarly. **Not documented on the `serve` OpenAI HTTP endpoint.** | [Base model card](https://huggingface.co/google/gemma-4-E2B-it), [CLI usage guide](https://developers.google.com/edge/litert-lm/cli/usage), [Python API guide](https://developers.google.com/edge/litert-lm/python) |
| Long context | Native Gemma 4 E2B context window is **128K tokens**, but the litert-community model card's own benchmark note says "the model can support up to 32k context length" for this on-device `.litertlm` checkpoint — a real discrepancy between the base model spec and the packaged/quantized runtime checkpoint that should be verified empirically before relying on it, since vig's article/long-video transcripts can be long. | [google/gemma-4-E2B-it card](https://huggingface.co/google/gemma-4-E2B-it) vs. [litert-community model card](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm) |
| Function/tool calling | Supported, but the execution model differs from Gemini's: LiteRT-LM's tool loop is closed within the CLI/runtime process itself (a `preset.py` defines Python functions the *engine* calls directly), not a caller-supplied per-request `tools` schema that the vig backend would execute and post back — this doesn't currently matter for vig since `gemini.py` has no function-calling usage today, but it means the two models are not drop-in equivalent if tool use is added later. | [CLI usage guide](https://developers.google.com/edge/litert-lm/cli/usage) |

---

## 6. Practical integration sketch (shape only, not implementation)

Given everything above, the smallest viable integration path that respects what the runtime actually offers, split by which of vig's existing Gemini call sites it could realistically cover:

1. **Sidecar process on the VPS.** Run `litert-lm serve --host 127.0.0.1 --port 9379 --backend=cpu` as a systemd-managed service alongside the existing `api`/`worker`/`transcript-service` containers, with the `gemma-4-E2B-it-litert-lm` checkpoint pre-pulled into its local model registry at provisioning time (avoids a cold Hugging Face download per boot). Bind to localhost only — same trust boundary as `transcript_server.py`'s existing host-sidecar pattern in this repo.
2. **Thin HTTP client for the text-only paths.** A new `src/services/litert.py` mirroring `generate()`'s signature (`prompt`, `model`, `schema`) that POSTs to `http://127.0.0.1:9379/v1/chat/completions` using the project's existing `httpx`-based patterns, feeding article/repo/document enrichment through it. This is the safe, well-documented slice — it only needs what `litert-lm serve`'s OpenAI-shaped endpoint openly supports (text chat + streaming).
3. **Do not route the vision call sites (`call_gemini_vision`, `call_gemini_photo_links`, `select_informative_screenshots`) through `litert-lm serve`** until Google documents image input on that endpoint. If self-hosting vision is still wanted, the verified path is a second, purpose-built wrapper that imports `litert_lm` directly in Python (`Engine` + `Conversation` + `Content.ImageFile()`), replicating what the CLI's `--attachment` flag does, and exposes whatever minimal HTTP contract vig's `gemini.py`-shaped callers need — i.e., writing the "vision server" Google hasn't shipped yet, rather than trusting an undocumented feature of the OpenAI-compatible one.
4. **Config gate, not a hard swap.** Add a settings flag (e.g. `ENRICHMENT_BACKEND=gemini|litert`) so the litert-lm path can be enabled per-pipeline (start with article/repo/document, the text-only ones) while vision-heavy short-video/photo paths keep using the hosted Gemini API until the JSON-schema-on-`serve` and vision-on-`serve` questions are answered by Google or verified by hand against a running `litert-lm serve` instance.
5. **Keep Gemini as the fallback**, not just for the unverified feature gaps above, but because the measured CPU throughput (§4) is meaningfully slower than a hosted frontier model and a budget VPS's decode speed is unverified until benchmarked on the actual target hardware.

---

## Sources

- [litert-community/gemma-4-E2B-it-litert-lm — model card](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm)
- [litert-community/gemma-4-E2B-it-litert-lm — HF API metadata](https://huggingface.co/api/models/litert-community/gemma-4-E2B-it-litert-lm)
- [google/gemma-4-E2B-it — base instruction-tuned model card](https://huggingface.co/google/gemma-4-E2B-it)
- [google/gemma-4-E2B-it — HF API metadata](https://huggingface.co/api/models/google/gemma-4-E2B-it)
- [Gemma 4 license (Apache 2.0 + Google terms)](https://ai.google.dev/gemma/docs/gemma_4_license)
- [Gemma 4 technical report (arXiv:2607.02770)](https://arxiv.org/abs/2607.02770)
- [google-ai-edge/LiteRT-LM — GitHub repo](https://github.com/google-ai-edge/LiteRT-LM)
- [google-ai-edge/LiteRT-LM — README (raw)](https://github.com/google-ai-edge/LiteRT-LM/blob/main/README.md)
- [LiteRT-LM — Overview docs](https://developers.google.com/edge/litert-lm/overview)
- [LiteRT-LM — CLI docs](https://developers.google.com/edge/litert-lm/cli)
- [LiteRT-LM — CLI installation guide](https://developers.google.com/edge/litert-lm/cli/installation)
- [LiteRT-LM — CLI usage guide (function calling, vision attachments)](https://developers.google.com/edge/litert-lm/cli/usage)
- [LiteRT-LM — OpenAI-Compatible Server docs](https://developers.google.com/edge/litert-lm/cli/openai_server)
- [LiteRT-LM — Python API guide](https://developers.google.com/edge/litert-lm/python)
- [LiteRT-LM — Build-and-run-from-source guide](https://github.com/google-ai-edge/LiteRT-LM/blob/main/docs/getting-started/build-and-run.md)
- [LiteRT-LM — Constrained decoding docs (LLGuidance, JSON Schema)](https://github.com/google-ai-edge/LiteRT-LM/blob/main/docs/api/cpp/constrained-decoding.md)
- Internal (for §5/§6 grounding, not a web source): `src/services/gemini.py` in this repo

