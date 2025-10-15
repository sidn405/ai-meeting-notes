# app_uploads.py
import os, time, uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
import boto3
from botocore.config import Config

# ---------- flexible env + lazy client ----------
def _first(*names: str) -> Optional[str]:
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return None

def _cfg():
    endpoint = _first("S3_ENDPOINT", "B2_S3_ENDPOINT") or "https://s3.us-west-004.backblazeb2.com"
    region   = _first("S3_REGION", "B2_S3_REGION") or "us-west-004"
    bucket   = _first("S3_BUCKET", "B2_BUCKET")
    access   = _first("AWS_ACCESS_KEY_ID", "S3_ACCESS_KEY_ID", "B2_ACCESS_KEY_ID")
    secret   = _first("AWS_SECRET_ACCESS_KEY", "S3_SECRET_ACCESS_KEY", "B2_SECRET_ACCESS_KEY")
    public   = _first("S3_PUBLIC_BASE_URL", "B2_PUBLIC_BASE_URL")
    if not public and bucket:
        public = f"{endpoint.rstrip('/')}/{bucket}"
    raw      = os.getenv("CLIPNOTE_RAW_PREFIX", "raw/")
    assets   = os.getenv("CLIPNOTE_ASSETS_PREFIX", "assets/")
    # default 500 MB (was 25)
    part_mb  = int(os.getenv("MAX_PART_SIZE_MB", "500"))
    return {
        "endpoint": endpoint, "region": region, "bucket": bucket,
        "access": access, "secret": secret, "public": public,
        "raw": raw, "assets": assets, "part_mb": part_mb,
    }

def _require_cfg():
    c = _cfg()
    missing = [k for k in ("bucket", "access", "secret") if not c[k]]
    if missing:
        raise HTTPException(status_code=500, detail=f"Storage env missing: {', '.join(missing)}")
    return c

def _s3():
    c = _require_cfg()
    return boto3.client(
        "s3",
        region_name=c["region"],
        endpoint_url=c["endpoint"],
        aws_access_key_id=c["access"],
        aws_secret_access_key=c["secret"],
        config=Config(
            s3={"addressing_style": "virtual"},  # required for Backblaze-style endpoints
            signature_version="s3v4",
            retries={"max_attempts": 4, "mode": "standard"},
        ),
    )

router = APIRouter(prefix="/uploads", tags=["uploads"])

# ---------- helpers ----------
ALLOWED_EXTS = {".mp3", ".m4a", ".wav", ".mp4"}
CANONICAL_CT = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",  # m4a == audio/mp4
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
}
CT_ALIASES = {
    "audio/x-m4a": "audio/mp4",
    "audio/m4a":   "audio/mp4",
    "audio/x-wav": "audio/wav",
    "audio/wave":  "audio/wav",
    "audio/x-pn-wav": "audio/wav",
}

def _ext(name: str) -> str:
    import os
    return os.path.splitext(name.lower())[1]

def _sanitize_filename(name: str) -> str:
    keep = "".join(c for c in name if c.isalnum() or c in (".","-","_"))
    return keep or "file"

def _now_ts() -> int:
    return int(time.time())

def _canonical_ct(filename: str, requested_ct: Optional[str]) -> str:
    ext = _ext(filename)
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .mp3, .m4a, .wav, .mp4 allowed",
        )
    req = (requested_ct or "").lower().strip()
    _ = CT_ALIASES.get(req, req)  # normalize (not strictly needed since we pick by ext)
    return CANONICAL_CT[ext]

# ---------- models ----------
class PresignRequest(BaseModel):
    filename: str
    content_type: Optional[str] = None
    folder: Optional[str] = "raw"
    ttl_seconds: Optional[int] = 3600

class PresignResponse(BaseModel):
    key: str
    url: str
    method: str = "PUT"
    headers: dict
    public_url: Optional[str] = None

class MultiStartReq(BaseModel):
    filename: str
    content_type: Optional[str] = None
    folder: Optional[str] = "raw"

class MultiStartRes(BaseModel):
    key: str
    upload_id: str
    part_size: int

class PartURLReq(BaseModel):
    key: str
    upload_id: str
    part_number: int
    ttl_seconds: Optional[int] = 3600

class PartURLRes(BaseModel):
    url: str
    method: str = "PUT"
    headers: dict = {}

class CompleteReq(BaseModel):
    key: str
    upload_id: str
    parts: List[dict]  # [{"ETag":"...", "PartNumber":1}, ...]

class CompleteRes(BaseModel):
    location: str
    version_id: Optional[str] = None
    public_url: Optional[str] = None

# ---------- routes ----------
@router.post("/presign", response_model=PresignResponse)
def presign_simple(req: PresignRequest):
    c = _require_cfg()
    s3 = _s3()
    prefix = c["raw"] if req.folder == "raw" else c["assets"]
    safe_name = _sanitize_filename(req.filename)
    key = f"{prefix}{_now_ts()}_{uuid.uuid4().hex}_{safe_name}"
    content_type = _canonical_ct(req.filename, req.content_type)

    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": c["bucket"], "Key": key, "ContentType": content_type},
        ExpiresIn=min(req.ttl_seconds or 3600, 7 * 24 * 3600),
        HttpMethod="PUT",
    )
    public_url = f"{c['public'].rstrip('/')}/{key}"
    return PresignResponse(key=key, url=url, headers={"Content-Type": content_type}, public_url=public_url)

@router.post("/multipart/start", response_model=MultiStartRes)
def multipart_start(req: MultiStartReq):
    c = _require_cfg()
    s3 = _s3()
    prefix = c["raw"] if req.folder == "raw" else c["assets"]
    safe_name = _sanitize_filename(req.filename)
    key = f"{prefix}{_now_ts()}_{uuid.uuid4().hex}_{safe_name}"
    content_type = _canonical_ct(req.filename, req.content_type)

    try:
        resp = s3.create_multipart_upload(Bucket=c["bucket"], Key=key, ContentType=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create multipart failed: {e}")

    part_size = c["part_mb"] * 1024 * 1024
    return MultiStartRes(key=key, upload_id=resp["UploadId"], part_size=part_size)

@router.post("/multipart/part-url", response_model=PartURLRes)
def multipart_part_url(req: PartURLReq):
    c = _require_cfg()
    s3 = _s3()
    try:
        url = s3.generate_presigned_url(
            ClientMethod="upload_part",
            Params={"Bucket": c["bucket"], "Key": req.key, "UploadId": req.upload_id, "PartNumber": req.part_number},
            ExpiresIn=min(req.ttl_seconds or 3600, 7 * 24 * 3600),
            HttpMethod="PUT",
        )
        return PartURLRes(url=url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Part presign failed: {e}")

@router.post("/multipart/complete", response_model=CompleteRes)
def multipart_complete(req: CompleteReq):
    c = _require_cfg()
    s3 = _s3()
    try:
        out = s3.complete_multipart_upload(
            Bucket=c["bucket"],
            Key=req.key,
            UploadId=req.upload_id,
            MultipartUpload={"Parts": sorted(req.parts, key=lambda p: p["PartNumber"])},
        )
        public_url = f"{c['public'].rstrip('/')}/{req.key}"
        return CompleteRes(location=out.get("Location", ""), version_id=out.get("VersionId"), public_url=public_url)
    except Exception as e:
        try:
            s3.abort_multipart_upload(Bucket=c["bucket"], Key=req.key, UploadId=req.upload_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Complete failed: {e}")

@router.get("/debug/head")
def head(key: str = Query(...)):
    c = _require_cfg()
    s3 = _s3()
    try:
        r = s3.head_object(Bucket=c["bucket"], Key=key)
        return {"ok": True, "size": r["ContentLength"], "etag": r["ETag"], "content_type": r.get("ContentType")}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
