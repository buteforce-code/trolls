"""
Image generation tools for the blog agent.
  - generate_imagen: Vertex AI Imagen via google-genai client
  - vision_qa_check: Gemini Vision gate — flags text/spelling errors in images
  - upload_to_supabase: Upload PNG bytes to Supabase Storage
  - generate_and_qa: Full pipeline (generate → QA → upload) with retries
  - ensure_bucket: Idempotent bucket bootstrap
"""
from __future__ import annotations
import json
import os
import uuid
from typing import Optional

from supabase import create_client, Client

BUCKET_NAME = "blog-images"
_MAX_QA_RETRIES = 3


def _genai_client():
    from google import genai

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true"

    if use_vertex and project:
        return genai.Client(vertexai=True, project=project, location=location)

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_AI_API_KEY", "")
    return genai.Client(api_key=api_key)


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


def generate_imagen(prompt: str, aspect_ratio: str = "16:9") -> Optional[bytes]:
    """
    Generate an image via Vertex AI Imagen. Returns PNG bytes or None on failure.
    aspect_ratio: "16:9" hero | "4:3" inline | "1:1" square
    """
    from google.genai import types as genai_types

    model = os.environ.get("IMAGEN_MODEL", "imagen-3.0-generate-001")
    client = _genai_client()

    try:
        response = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                safety_filter_level="BLOCK_ONLY_HIGH",
                person_generation="ALLOW_ADULT",
            ),
        )
        if response.generated_images:
            return response.generated_images[0].image.image_bytes
        return None
    except Exception as e:
        print(f"  [imagen] Generation error: {e}", flush=True)
        return None


def vision_qa_check(image_bytes: bytes) -> dict:
    """
    Run Gemini Vision QA on an image.
    Returns {"ok": bool, "issues": list[str]}
    Fails open (ok=True) to avoid blocking the publish pipeline on transient errors.
    """
    from google.genai import types as genai_types

    model = os.environ.get("ADK_GEMINI_MODEL", "gemini-2.0-flash")
    client = _genai_client()

    prompt = (
        "Inspect this image carefully for any visible text, words, labels, captions, "
        "or icon text. List every text string you can see. "
        "Flag any that is misspelled, garbled, broken, or contains odd characters. "
        'Return ONLY valid JSON: {"ok": true, "issues": []} '
        'or {"ok": false, "issues": ["description of problem"]}. '
        "If there is no text at all in the image, return {\"ok\": true, \"issues\": []}."
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt,
            ],
        )
        text = (response.text or "").strip()
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
        image_bytes = generate_imagen(prompt, aspect_ratio)
        if not image_bytes:
            print(f"  [imagen] Attempt {attempt}: generation returned nothing", flush=True)
            continue

        qa = vision_qa_check(image_bytes)
        if qa.get("ok", True):
            url = upload_to_supabase(image_bytes, slug, image_type)
            if url:
                print(f"  [imagen] {image_type} OK (attempt {attempt}): {url}", flush=True)
                return url
        else:
            print(f"  [qa] Attempt {attempt} failed: {qa.get('issues', [])}", flush=True)

    print(f"  [imagen] All {_MAX_QA_RETRIES} attempts failed for {image_type}", flush=True)
    return None
