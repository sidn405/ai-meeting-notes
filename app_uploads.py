# app_uploads.py
import os, time, uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
import boto3
from botocore.config import Config

# ---- ENV ----
B2_S3_ENDPOINT = os.environ.get("B2_S3_ENDPOINT", "https://s3.us-west-004.backblazeb2.com")
B2_S3_REGION   = os.environ.get("B2_S3_REGION",   "us-west-004")
B2_ACCESS      = os.environ["B2_ACCESS_KEY_ID"]
B2_SECRET      = os.environ["B2_SECRET_ACCESS_KEY"]
B2_BUCKET      = os.environ["B2_BUCKET"]
PUBLIC_BASE    = os.environ.get("B2_PUBLIC_BASE_URL", f"{B2_S3_ENDPOINT}/{B2_BUCKET}")
RAW_PREFIX     = os.environ.get("CLIPNOTE_RAW_PREFIX", "raw/")
ASSETS_PREFIX  = os.environ.get("CLIPNOTE_ASSETS_PREFIX", "assets/")
MAX_PART_MB    = int(os.environ.get("MAX_PART_SIZE_MB", "25"))

# ---- S3 CLIENT (Backblaze S3) ----
s3 = boto3.client(
    "s3",
    region_name=B2_S3_REGION,
    endpoint_url=B2_S3_ENDPOINT,
    aws_access_key_id=B2_ACCESS,
    aws_secret_access_key=B2_SECRET,
    config=Config(
        s3={"addressing_style": "virtual"},   # IMPORTANT for B2
        signature_version="s3v4",
        retries={"max_attempts": 4, "mode": "standard"},
    ),
)

router = APIRouter(prefix="/uploads", tags=["uploads"])

# ---- HELPERS ----
ALLOWED_EXTS = {".mp3", ".m4a", ".wav", ".mp4"}
CANONICAL_CT = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",   # m4a == audio/mp4
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
            detail=f"Only .mp3, .m4a, .wav, .mp4 allowed (got '{ext}')"
        )
    req = (requested_ct or "").lower().strip()
    req = CT_ALIASES.get(req, req)
    return CANONICAL_CT[ext]

# ---- MODELS ----
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

# ---- ROUTES ----
@router.post("/presign", response_model=PresignResponse)
def presign_simple(req: PresignRequest):
    prefix = RAW_PREFIX if req.folder == "raw" else ASSETS_PREFIX
    safe_name = _sanitize_filename(req.filename)
    key = f"{prefix}{_now_ts()}_{uuid.uuid4().hex}_{safe_name}"
    content_type = _canonical_ct(req.filename, req.content_type)

    try:
        url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": B2_BUCKET, "Key": key, "ContentType": content_type},
            ExpiresIn=min(req.ttl_seconds or 3600, 7*24*3600),
            HttpMethod="PUT",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presign failed: {e}")

    public_url = f"{PUBLIC_BASE}/{key}"
    return PresignResponse(
        key=key,
        url=url,
        headers={"Content-Type": content_type},
        public_url=public_url
    )

@router.post("/multipart/start", response_model=MultiStartRes)
def multipart_start(req: MultiStartReq):
    prefix = RAW_PREFIX if req.folder == "raw" else ASSETS_PREFIX
    safe_name = _sanitize_filename(req.filename)
    key = f"{prefix}{_now_ts()}_{uuid.uuid4().hex}_{safe_name}"
    content_type = _canonical_ct(req.filename, req.content_type)

    try:
        resp = s3.create_multipart_upload(Bucket=B2_BUCKET, Key=key, ContentType=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create multipart failed: {e}")

    part_size = MAX_PART_MB * 1024 * 1024
    return MultiStartRes(key=key, upload_id=resp["UploadId"], part_size=part_size)

@router.post("/multipart/part-url", response_model=PartURLRes)
def multipart_part_url(req: PartURLReq):
    try:
        url = s3.generate_presigned_url(
            ClientMethod="upload_part",
            Params={"Bucket": B2_BUCKET, "Key": req.key, "UploadId": req.upload_id, "PartNumber": req.part_number},
            ExpiresIn=min(req.ttl_seconds or 3600, 7*24*3600),
            HttpMethod="PUT",
        )
        return PartURLRes(url=url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Part presign failed: {e}")

@router.post("/multipart/complete", response_model=CompleteRes)
def multipart_complete(req: CompleteReq):
    try:
        out = s3.complete_multipart_upload(
            Bucket=B2_BUCKET,
            Key=req.key,
            UploadId=req.upload_id,
            MultipartUpload={"Parts": sorted(req.parts, key=lambda p: p["PartNumber"])},
        )
        public_url = f"{PUBLIC_BASE}/{req.key}"
        return CompleteRes(location=out.get("Location", ""), version_id=out.get("VersionId"), public_url=public_url)
    except Exception as e:
        try:
            s3.abort_multipart_upload(Bucket=B2_BUCKET, Key=req.key, UploadId=req.upload_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Complete failed: {e}")

# Optional: quick debug to check an object
@router.get("/debug/head")
def head(key: str = Query(...)):
    try:
        r = s3.head_object(Bucket=B2_BUCKET, Key=key)
        return {"ok": True, "size": r["ContentLength"], "etag": r["ETag"], "content_type": r.get("ContentType")}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
