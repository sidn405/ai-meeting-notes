# app/utils/storage.py
from __future__ import annotations
from pathlib import Path
import os, boto3
import re, secrets, time
from typing import Optional
from fastapi import UploadFile
from ..db import DATA_DIR  # we created this earlier in app/db.py
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_REGION = os.getenv("S3_REGION", "us-west-004")

def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

def save_bytes_s3(key: str, data: bytes) -> str:
    s3 = s3_client()
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data)
    return f"s3://{S3_BUCKET}/{key}"

def get_presigned_url(key: str, expires_in: int = 3600) -> str:
    s3 = s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires_in
    )

# Where we write files
UPLOADS_DIR = (DATA_DIR / "uploads")
TRANSCRIPTS_DIR = (DATA_DIR / "transcripts")
for d in (UPLOADS_DIR, TRANSCRIPTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

def _sanitize(name: str) -> str:
    name = name.strip().replace(" ", "_")
    return _SAFE.sub("-", name)

def _unique_name(stem: str, ext: str) -> str:
    ts = int(time.time())
    rand = secrets.token_hex(4)
    return f"{stem}-{ts}-{rand}{ext}"

def save_upload(file: UploadFile, subdir: Optional[str] = None) -> str:
    """
    Save an UploadFile to disk and return absolute path as a string.
    """
    sub = UPLOADS_DIR if not subdir else (DATA_DIR / subdir)
    sub.mkdir(parents=True, exist_ok=True)

    orig = file.filename or "upload.bin"
    stem, dot, ext = orig.rpartition(".")
    stem = _sanitize(stem or "upload")
    ext = f".{ext}" if dot else ""
    fname = _unique_name(stem, ext)
    dest = sub / fname

    with dest.open("wb") as out:
        # UploadFile.file is a SpooledTemporaryFile -> supports .read()
        out.write(file.file.read())

    return str(dest)

def save_text(content: str, title: str = "notes", subdir: Optional[str] = None, suffix: str = ".txt") -> str:
    """
    Save text content to disk and return absolute path as a string.
    """
    sub = TRANSCRIPTS_DIR if not subdir else (DATA_DIR / subdir)
    sub.mkdir(parents=True, exist_ok=True)

    stem = _sanitize(title or "notes")
    fname = _unique_name(stem, suffix)
    dest = sub / fname
    dest.write_text(content, encoding="utf-8")
    return str(dest)
