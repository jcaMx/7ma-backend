import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict


MANIFEST_FILENAME = "cache_manifest.json"
PIPELINE_CACHE_VERSION = 1


def _stable_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_for_value(value: Any) -> str:
    return hashlib.sha256(_stable_dumps(value).encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_manifest(output_dir: str) -> Dict[str, Any]:
    path = os.path.join(output_dir, MANIFEST_FILENAME)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_manifest(output_dir: str, manifest: Dict[str, Any]) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, MANIFEST_FILENAME)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    return path


def build_content_inputs(payload: Dict[str, Any], *, prompt_hash: str, model: str, temperature: Any) -> Dict[str, Any]:
    content_fields = {
        "name": payload.get("name"),
        "title": payload.get("title"),
        "company": payload.get("company"),
        "gender": payload.get("gender"),
        "bio": payload.get("bio"),
        "notes": payload.get("notes"),
    }
    return {
        "cache_version": PIPELINE_CACHE_VERSION,
        "content_fields": content_fields,
        "prompt_hash": prompt_hash,
        "model": model,
        "temperature": temperature,
    }


def build_audio_inputs(capability_scripts: Any, *, voice: str, model: str) -> Dict[str, Any]:
    return {
        "cache_version": PIPELINE_CACHE_VERSION,
        "voice": voice,
        "model": model,
        "capability_scripts": capability_scripts,
    }


def build_slides_inputs(content_dict: Dict[str, Any], *, presentation_id: str) -> Dict[str, Any]:
    relevant = {
        "user_input": content_dict.get("user_input"),
        "fictional_profile": content_dict.get("fictional_profile"),
        "capability_use_cases": content_dict.get("capability_use_cases"),
        "capability_scripts": content_dict.get("capability_scripts"),
        "presentation_id": presentation_id,
    }
    return {
        "cache_version": PIPELINE_CACHE_VERSION,
        "slides_content": relevant,
    }


def build_deck_inputs(combined_output: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cache_version": PIPELINE_CACHE_VERSION,
        "combined_output": combined_output,
    }
