import logging
from ..config import get_settings
import httpx

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
settings = get_settings()

SUMMARY_SYSTEM_PROMPT = (
    "You are an expert meeting notes assistant. Produce: "
    "1) Executive Summary (5 bullets), "
    "2) Key Decisions (bullets), "
    "3) Action Items as a table with columns: Owner, Task, Due Date, Priority. "
    "Be concise, factual, and use names/dates from the transcript when available."
)

async def _ollama_complete(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{settings.ollama_base}/api/generate", json={"model": settings.ollama_model, "prompt": prompt})
        r.raise_for_status()
        return r.json().get("response", "")

async def _openai_complete(prompt: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_key)
    r = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return r.choices[0].message.content

async def summarize(transcript: str, title: str) -> dict:
    prompt = f"Meeting Title: {title}\n\nTranscript (verbatim; may be imperfect):\n{transcript}\n\nGenerate the required sections."
    try:
        if settings.llm_provider == "ollama":
            text = await _ollama_complete(prompt)
        else:
            text = await _openai_complete(prompt)
    except Exception as e:
        logger.exception("LLM error; returning minimal fallback")
        text = minimal_fallback_summary(title, transcript) + "\n\n(Note: LLM error; fallback used.)"
    return {"title": title, "summary": text}

def minimal_fallback_summary(title: str, transcript: str) -> str:
    # naive fallback: first few sentences and basic table scaffold
    import re
    sentences = re.split(r'(?<=[.!?])\s+', (transcript or "").strip())
    bullets = "\n".join(f"- {s.strip()}" for s in sentences[:5] if s.strip()) or "- (insufficient transcript)"
    decisions = "- (no explicit decisions detected)"
    table = "\n".join([
        "| Owner | Task | Due Date | Priority |",
        "|-|-|-|-|",
        "| (owner) | (task) | (date) | (prio) |"
    ])
    return f"""# Meeting Notes: {title}

## Executive Summary
{bullets}

## Key Decisions
{decisions}

## Action Items
{table}
"""
