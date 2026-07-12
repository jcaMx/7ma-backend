import hashlib
import json
import logging
import os
import re
import traceback

from audio_generator import generate_tts_audio_from_file
from config import RESULT_DELIVERY_MODE
from content_generator import config as content_config
from content_generator import run_pipeline, sanitize_filename
from services.cache_manifest import (
    build_audio_inputs,
    build_content_inputs,
    build_deck_inputs,
    build_slides_inputs,
    load_manifest,
    save_manifest,
    sha256_for_value,
    utc_now_iso,
)
from services.email_utils import send_email_api
from services.jobs import jobs, jobs_lock
from slide_updater import slide_map, update_slides

logger = logging.getLogger(__name__)


CONTENT_OUTPUT_FILES = (
    "bio.json",
    "audience_description.json",
    "fictional_profile.json",
    "capability_scripts.json",
    "capability_use_cases.json",
    "combined_output.json",
)


def _file_sha256(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _remove_file_if_exists(path: str) -> None:
    if os.path.isfile(path):
        os.remove(path)


def _clear_generated_content(output_dir: str) -> None:
    for filename in CONTENT_OUTPUT_FILES:
        _remove_file_if_exists(os.path.join(output_dir, filename))


def _clear_audio_cache(audio_dir: str) -> None:
    if not os.path.isdir(audio_dir):
        return
    for filename in os.listdir(audio_dir):
        if filename.lower().endswith(".mp3"):
            _remove_file_if_exists(os.path.join(audio_dir, filename))


def _load_json_if_exists(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _extract_presentation_id(slides_url: str | None) -> str | None:
    if not slides_url:
        return None
    match = re.search(r"/presentation/d/([a-zA-Z0-9_-]+)", slides_url)
    return match.group(1) if match else None


def _resolve_output_dir(payload: dict) -> tuple[str, str]:
    folder_name = payload.get("folder_path") or payload.get("name") or "anonymous"
    safe_name = sanitize_filename(folder_name)
    output_dir = os.path.join("output", safe_name)
    os.makedirs(output_dir, exist_ok=True)
    return safe_name, output_dir


def _send_result_email(email: str | None, slides_url: str) -> None:
    if RESULT_DELIVERY_MODE not in ("email", "both") or not email:
        return
    send_email_api(
        to_email=email,
        body=slides_url,
    )


def run_full_pipeline(request_id: str, payload: dict):
    """
    Full 7MA pipeline for a given request ID.
    Updates jobs[request_id] with status, slides URL, or error.
    """
    logger.info("Pipeline started for %s", request_id)
    try:
        safe_name, output_dir = _resolve_output_dir(payload)
        prompts_hash = _file_sha256("prompts.md") if os.path.exists("prompts.md") else ""
        manifest = load_manifest(output_dir)
        force_regenerate = bool(payload.get("force_regenerate"))
        force_audio = bool(payload.get("force_audio"))
        force_slides = bool(payload.get("force_slides"))
        force_new_presentation = bool(payload.get("force_new_presentation"))

        initial_content_inputs = build_content_inputs(
            payload,
            prompt_hash=prompts_hash,
            model=content_config.get("model"),
            temperature=content_config.get("temperature"),
        )
        initial_content_hash = sha256_for_value(initial_content_inputs)

        if force_regenerate or (
            manifest.get("content_input_hash")
            and manifest.get("content_input_hash") != initial_content_hash
        ):
            logger.info("Content cache miss for %s; clearing stale generated sections", safe_name)
            _clear_generated_content(output_dir)
            manifest = {}

        result = run_pipeline(payload)
        logger.info("Content pipeline completed for %s", request_id)

        combined_output_path = os.path.join(output_dir, "combined_output.json")
        combined_output = _load_json_if_exists(combined_output_path) or result
        runtime = combined_output.get("_runtime", {})

        content_inputs = build_content_inputs(
            payload,
            prompt_hash=prompts_hash,
            model=runtime.get("model"),
            temperature=runtime.get("temperature"),
        )
        content_hash = sha256_for_value(content_inputs)

        capability_json_path = os.path.join(output_dir, "capability_scripts.json")
        audio_dir = os.path.join(output_dir, "audio_files")
        audio_hash = None

        if result.get("capability_scripts"):
            with open(capability_json_path, "w", encoding="utf-8") as handle:
                json.dump(result["capability_scripts"], handle, indent=2, ensure_ascii=False)

            generate_audio_env = os.getenv("GENERATE_AUDIO", "true").lower() == "true"
            if generate_audio_env:
                audio_inputs = build_audio_inputs(
                    result["capability_scripts"],
                    voice=str(payload.get("audio_voice") or "ash"),
                    model=str(payload.get("audio_model") or "tts-1"),
                )
                audio_hash = sha256_for_value(audio_inputs)
                audio_cache_hit = (
                    not force_audio
                    and manifest.get("audio_input_hash") == audio_hash
                    and os.path.isdir(audio_dir)
                    and any(name.lower().endswith(".mp3") for name in os.listdir(audio_dir))
                )

                if audio_cache_hit:
                    logger.info("Audio cache hit for %s; reusing generated MP3 files", request_id)
                else:
                    if force_audio or (
                        manifest.get("audio_input_hash")
                        and manifest.get("audio_input_hash") != audio_hash
                    ):
                        _clear_audio_cache(audio_dir)
                    generate_tts_audio_from_file(
                        capability_json_path,
                        voice=str(payload.get("audio_voice") or "ash"),
                        model=str(payload.get("audio_model") or "tts-1"),
                        overwrite=False,
                    )
                    logger.info("Audio generation completed for %s", request_id)
            else:
                logger.info("Audio generation skipped for %s (GENERATE_AUDIO is false)", request_id)

        presentation_id = payload.get("presentation_id") or os.getenv("PRESENTATION_ID")
        if not presentation_id:
            raise ValueError(
                "presentation_id is required. Provide it in the request payload or set PRESENTATION_ID environment variable."
            )

        slides_inputs = build_slides_inputs(result, presentation_id=presentation_id)
        slides_inputs["audio_input_hash"] = audio_hash
        slides_hash = sha256_for_value(slides_inputs)
        cached_slides_url = manifest.get("slides_url")
        cached_presentation_copy_id = manifest.get("presentation_copy_id")

        if not force_slides and manifest.get("slides_input_hash") == slides_hash and cached_slides_url:
            slides_url = cached_slides_url
            logger.info("Slides cache hit for %s; reusing %s", request_id, slides_url)
        else:
            target_presentation_id = cached_presentation_copy_id or presentation_id
            create_new_presentation = cached_presentation_copy_id is None
            if force_new_presentation:
                target_presentation_id = presentation_id
                create_new_presentation = True

            slides_url = update_slides(
                target_presentation_id,
                slide_map,
                result,
                audio_dir=audio_dir,
                create_new_presentation=create_new_presentation,
                user_inputs=payload,
            )
            logger.info("Slides updated for %s -> %s", request_id, slides_url)

        presentation_copy_id = _extract_presentation_id(slides_url) or cached_presentation_copy_id
        deck_hash = sha256_for_value(build_deck_inputs(combined_output))

        save_manifest(
            output_dir,
            {
                "cache_version": 1,
                "updated_at": utc_now_iso(),
                "request_id": request_id,
                "output_dir": os.path.abspath(output_dir),
                "folder_path": safe_name,
                "runtime": runtime,
                "content_input_hash": content_hash,
                "audio_input_hash": audio_hash,
                "slides_input_hash": slides_hash,
                "deck_input_hash": deck_hash,
                "slides_url": slides_url,
                "presentation_copy_id": presentation_copy_id,
            },
        )

        with jobs_lock:
            jobs[request_id]["status"] = "completed"
            jobs[request_id]["slides_url"] = slides_url
            jobs[request_id]["email"] = payload.get("email")
            jobs[request_id]["audio_dir"] = audio_dir if os.path.isdir(audio_dir) else None
            jobs[request_id]["output_dir"] = os.path.abspath(output_dir)
            jobs[request_id]["folder_path"] = safe_name

        _send_result_email(payload.get("email"), slides_url)
    except Exception as exc:
        with jobs_lock:
            jobs[request_id]["status"] = "error"
            jobs[request_id]["error"] = str(exc)
        logger.exception("Pipeline error processing request %s", request_id)
        traceback.print_exc()
