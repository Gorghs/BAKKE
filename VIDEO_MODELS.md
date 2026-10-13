# Video model evaluation

Researched October 2026. This file records which prompt-to-video providers BAKKE
could use, what they cost and cap, and why the code targets fal.ai first.
Numbers drift, so treat pricing rows as "check before you buy".

## What BAKKE needs

- Text-to-video only. No audio. The mock renderer adds labels in ffmpeg.
- Clips of 6 to 12 seconds at 16:9, 720p or better.
- An async submit and poll API. Video jobs run in the worker and must not hold
  a connection open for minutes.
- Prompt room for the expanded visual prompt, target under 1000 characters, hard
  cap 2500.
- Cheap trial credits. This is a demo pipeline, not a production render farm.

## Candidates

### fal.ai (aggregator) — chosen

One API key reaches Kling, Veo, Hailuo, Seedance and the rest of the fal
gallery. $20 trial credit with a business email when we signed up for research.

The queue contract is the reason it won:

```text
POST https://queue.fal.run/<model-id>     Authorization: Key <FAL_KEY>
  -> {request_id, status_url, response_url}
GET  <status_url>   -> IN_QUEUE | IN_PROGRESS | COMPLETED (error field on failure)
GET  <response_url> -> {video: {url, ...}}
```

That maps one to one onto `_HttpVideoProvider._submit` / `_poll` in
`app/providers/video.py`. We verified the shapes against fal's queue
documentation in October 2026, before writing the adapter.

Prompt limits are per model and mostly looser than the vendors' own APIs. For
example the same Kling model allows longer prompts through fal than through
api.klingai.com. Pricing is per model, listed on each fal model page.

Verdict: default real provider. Set `VIDEO_GENERATION_PROVIDER=fal`, put the
fal key in `VIDEO_GENERATION_API_KEY`, and put a model id in
`VIDEO_GENERATION_MODEL` (example: `fal-ai/kling-video/v2.1/standard/text-to-video`).

### Kling official API

`POST api.klingai.com/v1/videos/text2video`, durations 5 or 10 seconds on v2,
720p to 4K. Prompt limit is 500 characters on the official endpoint, which is
too tight for our shot-list prompt without cutting it down. Free credits exist
in the consumer app, the API runs on purchased credits. The adapter in
`video.py` predates this evaluation and its endpoint shape has not been
re-verified.

Verdict: fallback if fal ever disappoints. Not first choice because of the
500-character prompt cap and a second billing relationship.

### MiniMax Hailuo official

`POST api.minimaxi.com/v1/video_generation`, fixed 6 second clips at 720p,
prompt-only input, status queried at `/v1/query/video_generation`. Signup comes
with roughly 150 credits. The adapter exists in `video.py`.

Verdict: fine for a second opinion on the same prompt, 6 seconds is shorter
than our 12 second specs.

### Runway

Gen-4 and Gen-4.5 are strong, but the free credit is a one time 125 credits in
the consumer app, and API keys come from a separate developer account with no
free tier. The adapter in `video.py` points at `api.dev.runwayml.com`, a
development host that should not be trusted without re-reading Runway's docs.

Verdict: skip. Paying for a second provider before exhausting fal's credit
wastes money.

### Google Veo 3.1 via the Gemini API

4, 6 or 8 second clips at 720p, 1080p and 4K. Quality is the best in this
group. The price is also the highest: somewhere around $0.15 to $0.40 per
second depending on resolution, and the free tier returns 429 for video
generation. Clips carry a SynthID watermark. There is no adapter in the repo.

Verdict: worth a look when a demo has to impress a room. Not the default at
those rates.

### PixVerse

Daily free credits, clean exports, consumer web product. No documented public
API we would trust for a backend job.

Verdict: out.

### Sora

The Sora and Videos APIs were removed on September 24, 2026. Nothing to
evaluate.

## Settings summary

| Provider | Env value | Key | Model value |
|---|---|---|---|
| mock (default) | `mock` | none | none |
| fal.ai | `fal` | fal `FAL_KEY` value | fal model id, e.g. `fal-ai/kling-video/v2.1/standard/text-to-video` |
| Kling official | `kling` | Kling API key | Kling model name |
| Hailuo official | `hailuo` | MiniMax API key | e.g. `T2V-01-Director` |
| Runway | `runway` | Runway key | model name |

A missing key never breaks anything: the registry forces the mock provider and
the response carries `is_mock: true` with the DEVELOPMENT MOCK label.

## Prompt expansion LLM options

Expansion is a small LLM call: take the director's visual prompt, rewrite it
compact, keep every constraint and the NOT RECORDED FOOTAGE label. It runs
through the normal LLM provider, so it works with `LLM_PROVIDER=mock` for free
and switches to a real model when `OPENAI_API_KEY` is set.

`OPENAI_BASE_URL` points the OpenAI client at any compatible endpoint. The
options we researched in October 2026, all with some form of free access:

| Endpoint | Base URL | Free access |
|---|---|---|
| Groq | `https://api.groq.com/openai/v1` | free tier, rate capped per day |
| OpenRouter | `https://openrouter.ai/api/v1` | `:free` models, daily caps, higher after $10 credit |
| DeepSeek | `https://api.deepseek.com/v1` | small trial credit on signup, cheap after |
| Gemini (OpenAI layer) | `https://generativelanguage.googleapis.com/v1beta/openai/` | free tier with daily limits |
| Mistral | `https://api.mistral.ai/v1` | experiment tier |

All five take a normal `OPENAI_API_KEY`-style key, so the repo needs exactly
one new setting (`OPENAI_BASE_URL`) instead of a new provider class. With no
key, expansion falls back to the deterministic mock, which returns the prompt
unchanged.
