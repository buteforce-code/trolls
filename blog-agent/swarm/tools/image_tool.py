"""
Image generation tools for the blog agent — OpenAI backend.

  - images_enabled: read the ENABLE_IMAGES kill switch
  - generate_image:  OpenAI image API (dall-e-3 / gpt-image-1) → PNG bytes
  - vision_qa_check: OpenAI vision (gpt-4o) gate — flags text/spelling in images
  - upload_to_supabase: upload PNG bytes to Supabase Storage
  - generate_and_qa: full pipeline (generate → QA → upload) with retries
  - ensure_bucket: idempotent bucket bootstrap

Image generation is OFF by default (ENABLE_IMAGES=false). When disabled, the
caller (swarm/agents/imager.py) short-circuits before any of this runs, so no
OpenAI image spend happens. Flip ENABLE_IMAGES=true to turn it on.
"""
from __future__ import annotations
import base64
import json
import os
import uuid
from typing import Optional

from supabase import create_client, Client

BUCKET_NAME = "blog-images"
_MAX_QA_RETRIES = 3

# OpenAI image models support a fixed set of sizes, not arbitrary ratios.
# Map the planner's aspect_ratio hints onto the closest supported size.
#   dall-e-3:    1024x1024 | 1792x1024 | 1024x1792
#   gpt-image-1: 1024x1024 | 1536x1024 | 1024x1536
_SIZE_BY_RATIO_DALLE = {
    "16:9": "1792x1024",
    "4:3": "1792x1024",
    "1:1": "1024x1024",
    "9:16": "1024x1792",
    "3:4": "1024x1792",
}
_SIZE_BY_RATIO_GPTIMAGE = {
    "16:9": "1536x1024",
    "4:3": "1536x1024",
    "1:1": "1024x1024",
    "9:16": "1024x1536",
    "3:4": "1024x1536",
}


def images_enabled() -> bool:
    """Master kill switch. Images are opt-in."""
    return os.environ.get("ENABLE_IMAGES", "false").strip().lower() == "true"


def _openai_client():
    from openai import OpenAI

    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def ensure_bucket() -> None:
    """Idempotent: create the blog-images public bucket if it doesn't exist."""
    try:
        sb = _supabase()
        names = [b.name for b in sb.storage.list_buckets()]
        if BUCKET_NAME not in names:
            sb.storage.create_bucket(BUCKET_NAME, options={"public": True})
            print(f"  [storage] Created public bucket: {BUCKET_NAME}", flush=True)
    except Exception as e:
        print(f"  [storage] Bucket check failed: {e}", flush=True)


def _size_for(model: str, aspect_ratio: str) -> str:
    table = _SIZE_BY_RATIO_GPTIMAGE if model.startswith("gpt-image") else _SIZE_BY_RATIO_DALLE
    return table.get(aspect_ratio, "1024x1024")


def generate_image(prompt: str, aspect_ratio: str = "16:9") -> Optional[bytes]:
    """
    Generate an image via the OpenAI image API. Returns PNG bytes or None.
    Model is chosen by OPENAI_IMAGE_MODEL (default: dall-e-3).
    aspect_ratio: "16:9" hero | "4:3" inline | "1:1" square
    """
    model = os.environ.get("OPENAI_IMAGE_MODEL", "dall-e-3")
    size = _size_for(model, aspect_ratio)
    client = _openai_client()

    try:
        kwargs = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        # dall-e-3 returns a URL by default; force base64 so we get bytes directly.
        # gpt-image-1 always returns base64 and rejects response_format.
        if not model.startswith("gpt-image"):
            kwargs["response_format"] = "b64_json"
            kwargs["quality"] = "hd"

        response = client.images.generate(**kwargs)
        b64 = response.data[0].b64_json
        if b64:
            return base64.b64decode(b64)
        return None
    except Exception as e:
        print(f"  [image] Generation error ({model}): {e}", flush=True)
        return None


def vision_qa_check(image_bytes: bytes) -> dict:
    """
    Run OpenAI vision QA on an image.
    Returns {"ok": bool, "issues": list[str]}.
    Fails open (ok=True) to avoid blocking the publish pipeline on transient errors.
    """
    model = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o")
    client = _openai_client()

    data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "Inspect this image carefully for any visible text, words, labels, captions, "
        "or icon text. List every text string you can see. "
        "Flag any that is misspelled, garbled, broken, or contains odd characters. "
        'Return ONLY valid JSON: {"ok": true, "issues": []} '
        'or {"ok": false, "issues": ["description of problem"]}. '
        'If there is no text at all in the image, return {"ok": true, "issues": []}.'
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0:
            return json.loads(text[start:end])
        return {"ok": True, "issues": []}
    except Exception as e:
        print(f"  [qa] Vision check error: {e}", flush=True)
        return {"ok": True, "issues": []}


def upload_to_supabase(image_bytes: bytes, slug: str, image_type: str) -> Optional[str]:
    """
    Upload PNG bytes to Supabase Storage.
    Returns the public URL or None on failure.
    """
    filename = f"{slug}/{image_type}-{uuid.uuid4().hex[:8]}.png"

    try:
        sb = _supabase()
        sb.storage.from_(BUCKET_NAME).upload(
            path=filename,
            file=image_bytes,
            file_options={"content-type": "image/png", "cache-control": "86400"},
        )
        return sb.storage.from_(BUCKET_NAME).get_public_url(filename)
    except Exception as e:
        print(f"  [storage] Upload failed: {e}", flush=True)
        return None


def generate_and_qa(
    prompt: str,
    aspect_ratio: str,
    slug: str,
    image_type: str,
) -> Optional[str]:
    """
    Full pipeline: generate → QA (up to 3 retries) → upload → return public URL.
    Returns None if all retries fail.
    """
    for attempt in range(1, _MAX_QA_RETRIES + 1):
        image_bytes = generate_image(prompt, aspect_ratio)
        if not image_bytes:
            print(f"  [image] Attempt {attempt}: generation returned nothing", flush=True)
            continue

        qa = vision_qa_check(image_bytes)
        if qa.get("ok", True):
            url = upload_to_supabase(image_bytes, slug, image_type)
            if url:
                print(f"  [image] {image_type} OK (attempt {attempt}): {url}", flush=True)
                return url
        else:
            print(f"  [qa] Attempt {attempt} failed: {qa.get('issues', [])}", flush=True)

    print(f"  [image] All {_MAX_QA_RETRIES} attempts failed for {image_type}", flush=True)
    return None
