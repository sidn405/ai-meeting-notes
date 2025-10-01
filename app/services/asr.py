# app/services/asr.py
from pathlib import Path
from functools import lru_cache
import os, subprocess
from ..config import get_settings
from .summarizer import logger

settings = get_settings()

# ---------- optional pre-processing (normalize, mono 16k, light denoise) ----------
def preprocess_audio(src_path: str) -> str:
    src = Path(src_path)
    out = src.with_suffix(".pre.wav")
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-ac", "1", "-ar", "16000",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=80,lowpass=f=8000,afftdn=nf=-25",
        str(out)
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return str(out)
    except Exception:
        return str(src)

# ---------- runtime options ----------
CURRENT_OPTS = {
    "model_size": settings.whisper_model_size,     # tiny|base|small|medium|large-v3
    "device": None,                                # "cpu" or "cuda" (auto if None)
    "compute_type": None,                          # e.g. "int8", "float16", "auto"
}

def configure_local_asr(model_size: str | None = None,
                        device: str | None = None,
                        compute_type: str | None = None) -> None:
    changed = False
    if model_size and model_size != CURRENT_OPTS["model_size"]:
        CURRENT_OPTS["model_size"] = model_size; changed = True
    if device and device != CURRENT_OPTS["device"]:
        CURRENT_OPTS["device"] = device; changed = True
    if compute_type and compute_type != CURRENT_OPTS["compute_type"]:
        CURRENT_OPTS["compute_type"] = compute_type; changed = True
    if changed:
        _get_local_model.cache_clear()

@lru_cache(maxsize=1)
def _get_local_model():
    # resolve device/compute
    device = CURRENT_OPTS["device"]
    if not device:
        env = os.getenv("WHISPER_DEVICE", "auto").lower()
        device = "cuda" if env in ("cuda", "gpu", "nvidia") else "cpu"

    ct = CURRENT_OPTS["compute_type"]
    if not ct:
        ct = os.getenv("WHISPER_COMPUTE_TYPE", "int8" if device == "cpu" else "float16")

    from faster_whisper import WhisperModel
    model = WhisperModel(
        CURRENT_OPTS["model_size"],
        device=device,
        compute_type=ct
    )
    logger.info(f"Loaded faster-whisper model={CURRENT_OPTS['model_size']} device={device} compute={ct}")
    return model

def transcribe_local(audio_path: str,
                     *,
                     language: str | None,
                     initial_prompt: str | None,
                     model_size: str | None = None,
                     device: str | None = None,
                     compute_type: str | None = None) -> str:
    configure_local_asr(model_size, device, compute_type)
    model = _get_local_model()
    processed = preprocess_audio(audio_path)

    beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
    best_of   = int(os.getenv("WHISPER_BEST_OF", "5"))
    min_sil   = int(os.getenv("WHISPER_MIN_SIL_MS", "300"))

    segments, info = model.transcribe(
        processed,
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": min_sil},
        beam_size=beam_size,
        best_of=best_of,
        condition_on_previous_text=True,
        temperature=[0.0, 0.2, 0.4],
        initial_prompt=initial_prompt,
    )
    text = " ".join(seg.text for seg in segments).strip()
    logger.info(f"ASR(local): lang={getattr(info,'language',None)} dur≈{getattr(info,'duration',0):.1f}s")
    return text

# --------- AssemblyAI (optional cloud) ---------
async def transcribe_assemblyai(audio_path: str, *, language: str | None, initial_prompt: str | None) -> str:
    import httpx
    if not settings.assemblyai_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY not set")
    data = Path(audio_path).read_bytes()
    headers = {"authorization": settings.assemblyai_key}
    async with httpx.AsyncClient(timeout=180) as client:
        up = await client.post("https://api.assemblyai.com/v2/upload", content=data, headers=headers)
        up.raise_for_status()
        audio_url = up.json()["upload_url"]
        payload = {
            "audio_url": audio_url,
            "language_code": language or "en",
            "punctuate": True, "format_text": True
        }
        job = await client.post("https://api.assemblyai.com/v2/transcript", json=payload, headers=headers)
        tid = job.json()["id"]
        while True:
            r = await client.get(f"https://api.assemblyai.com/v2/transcript/{tid}", headers=headers)
            j = r.json()
            if j.get("status") == "completed":
                return j.get("text", "")
            if j.get("status") == "error":
                raise RuntimeError(j)

# --------- Provider switch ---------
async def transcribe(audio_path: str,
                     *,
                     language: str | None = None,
                     initial_prompt: str | None = None,
                     model_size: str | None = None,
                     device: str | None = None,
                     compute_type: str | None = None) -> str:
    prov = settings.asr_provider.lower()
    if prov == "assemblyai":
        return await transcribe_assemblyai(audio_path, language=language, initial_prompt=initial_prompt)
    return transcribe_local(audio_path,
                            language=language, initial_prompt=initial_prompt,
                            model_size=model_size, device=device, compute_type=compute_type)
