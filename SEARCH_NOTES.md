# HF Vanished — search notes

Generated: 2026-09-16 (Australia/Sydney box; UTC timestamps in events.json)

## Goal

Public ledger of Hugging Face **model** access-kills: DISABLED / DELETED / GATED / PRIVATE / STRIPPED, with emphasis on uncensored/abliterated/refusal-related repos **and** notable top models.

## Methods used

### 1. Web search / fetch
- Queries for abliterated/uncensored/jailbreak removals, WizardLM-2 withdrawal, RunwayML SD1.5, Stability SD2, MPT/DBRX/Dolly, HF content-policy disables.
- Primary sources pulled:
  - 404 Media / PCMag / Reddit on **WizardLM-2** toxicity-testing pull (Apr 2024)
  - `huggingface/diffusers#9322` on **RunwayML HF org removal** (2024-08-29)
  - HF forum thread 170425 on **Stability SD2 family** disappearance (2025-11-14)
  - `vllm-project/vllm#31182` stating **mosaicml/mpt-7b** and **databricks/dbrx-instruct** deleted/unavailable (2025-12-22)
  - Owner discussion on `audnai/penclaw-GLM-5.3-abliterated` about HF content team removals

### 2. Hugging Face Hub API
- `GET /api/models/{id}` for `gated`, `disabled`, `private`, downloads, siblings, cardData.
- Search: `?search=abliterated|abliteration|uncensored|jailbreak|refusal|obliterated&limit=100&full=true` (multiple pages).
- Author scans: `audnai`, `huihui-ai`, `WizardLMTeam`, `runwayml`.
- **Finding:** disabled repos are often **hidden from search/author lists** but still return JSON when requested by exact ID (e.g. penclaw offensive-cyber: `disabled=true`).
- Unauthenticated **401** (`Invalid username or password`) is HF’s opaque response for private **or** deleted repos; combined with news/mirrors to classify DELETED vs PRIVATE.

### 3. Wayback / CDX
- Attempted CDX (`web.archive.org/cdx/search/cdx`) and `archive.org/wayback/available` for known model URLs.
- **Result:** Archive.org endpoints timed out / returned empty from this environment (likely rate-limit or egress block). Ledger therefore uses **wildcard** Wayback links (`/web/*/https://huggingface.co/...`) for follow-up, not verified snapshot timestamps.
- Cross-check substitutes used instead: contemporary news, GitHub issues, HF forums, and still-public mirrors.

### 4. Cross-checks
- Mirrors proving prior public life: `alpindale/WizardLM-2-8x22B`, `lucyknada/microsoft_WizardLM-2-7B`, `sd2-community/stable-diffusion-2-1`, `Comfy-Org/stable-diffusion-v1-5-archive`, `alpindale/dbrx-instruct`, many `*-Meta-Llama-3.1-8B-Instruct-abliterated*` quants.
- `runwayml/stable-diffusion-v1-5`: HTML page 401; API **307 →** `stable-diffusion-v1-5/stable-diffusion-v1-5` (successor created 2024-08-30). Counted as DELETED original org hosting.

## Counts in `data/events.json`

| status   | count |
|----------|------:|
| DISABLED | 1 |
| DELETED  | 24 |
| PRIVATE  | 6 |
| GATED    | 6 |
| STRIPPED | 0 |
| **Total**| **37** |

### Cluster breakdown
- **Abliterated / uncensored / offensive:** penclaw DISABLED+GATED (3), huihui Llama PRIVATE (5), failspy 70B-v3 PRIVATE (1), huihui/orcarouter GATED notables (4) → **13**
- **Notable top / vendor pullbacks:** WizardLM-2 (5), RunwayML SD1.x (2), Stability SD2 family (4), MosaicML MPT (7), Databricks DBRX+Dolly (6) → **24**

## What we did *not* invent
- No entries based only on rumor without API/HTTP or reputable report.
- Temporary Meta/Facebook org compromise (Jul 2023) omitted — models restored.
- Microsoft TRELLIS temporary outage omitted — repos restored.
- Datasets (e.g. AoPS MATH DMCA) omitted — ledger is model-focused.
- `filter=disabled` search returns `[]` — disabled models are not discoverable via that filter; must know IDs or use reports.

## Gaps / follow-ups for parent
1. Re-run Wayback CDX from a network that can reach archive.org; replace wildcards with concrete `web/YYYYMMDDhhmmss/...` links.
2. Hunt more `disabled=true` IDs (content-policy) — they won’t show in search.
3. STRIPPED (weights removed, card remains) needs per-repo sibling history / commit diffs; none confirmed this pass.
4. “Newly gated after previously open” is hard without Wayback; current GATED entries are **currently gated** abliterated/uncensored notables (plus penclaw content-team context). Promote/demote once snapshot proof exists.
5. Reddit “16TB deletion spree” thread timed out on fetch — worth manual review for additional abliterated IDs.

## Seed / known example
- **Included:** `audnai/penclaw-GLM-5.3-abliterated-for-offensive-cyber` (`disabled=true`, `gated=manual`).
