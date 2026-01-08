import concurrent.futures
import json
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

import chardet
import openai


def sanitize_filename(value):
    """Clean string to be safe for filenames."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value.strip().replace(" ", "_"))


def safe_load_json(path):
    """Load JSON with encoding detection."""
    with open(path, "rb") as f:
        raw_data = f.read()
        detected = chardet.detect(raw_data)
        encoding = detected["encoding"] or "utf-8"
        try:
            return json.loads(raw_data.decode(encoding))
        except Exception as e:  # pragma: no cover - diagnostic path
            print(f"⚠️ Fallback to UTF-8 for {path}: {e}")
            return json.loads(raw_data.decode("utf-8", errors="ignore"))


def _resolve_folder_prefix(input_json_path: str, output_dir: str) -> str:
    """Try to use user_inputs.folder_path; fallback to parent folder name."""
    base_dir = os.path.dirname(os.path.abspath(input_json_path))
    candidate_user_input = os.path.join(base_dir, "user_input.json")
    folder_name = None

    if os.path.exists(candidate_user_input):
        try:
            user_input = safe_load_json(candidate_user_input)
            folder_name = user_input.get("folder_path") or user_input.get("name")
        except Exception:
            folder_name = None

    if not folder_name:
        parent = os.path.basename(os.path.dirname(os.path.abspath(output_dir)))
        folder_name = parent or None

    if folder_name:
        return sanitize_filename(str(folder_name)).lower()
    return ""


@dataclass
class AudioJobResult:
    index: int
    filename: str
    skipped: bool = False
    error: Optional[str] = None


class AudioGenerator:
    def __init__(self, api_key: Optional[str] = None, voice: str = "ash", model: str = "tts-1") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.voice = voice
        self.model = model
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required to generate audio.")
        openai.api_key = self.api_key

    def _render_item(
        self,
        item: dict,
        index: int,
        output_dir: str,
        filename_key: str,
        prefix: str,
        overwrite: bool,
        folder_prefix: str = "",
        *,
        filepath: str | None = None,
        filename: str | None = None,
    ) -> AudioJobResult:
        text = item.get("script", "").strip()
        if not text:
            return AudioJobResult(index=index, filename="", skipped=True, error="missing script")

        if not filepath or not filename:
            raw_label = item.get(filename_key, f"item{index}")
            label_source = str(raw_label).strip().lower()
            first_word = re.search(r"[a-z0-9]+", label_source)
            if first_word:
                label = first_word.group(0)
            else:
                label = sanitize_filename(label_source)
            prefix_fragment = f"{folder_prefix}_" if folder_prefix else ""
            filename = f"{prefix_fragment}{prefix}_{index}_{label}.mp3"
            filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath) and not overwrite:
            return AudioJobResult(index=index, filename=filepath, skipped=True)

        try:
            response = openai.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format="mp3",
            )
            with open(filepath, "wb") as f:
                f.write(response.content)
            return AudioJobResult(index=index, filename=filepath)
        except Exception as exc:  # pragma: no cover - API call
            return AudioJobResult(index=index, filename=filepath, error=str(exc))

    def generate_from_items(
        self,
        items: Iterable[dict],
        output_dir: str,
        *,
        prefix: str = "capability",
        filename_key: str = "capability",
        overwrite: bool = False,
        max_workers: int = 4,
        folder_prefix: str = "",
    ) -> List[AudioJobResult]:
        os.makedirs(output_dir, exist_ok=True)
        futures = []
        results: List[AudioJobResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for idx, item in enumerate(items, start=1):
                filepath, filename = self._compute_audio_filename(
                    item,
                    idx,
                    output_dir,
                    filename_key,
                    prefix,
                    folder_prefix,
                )

                if os.path.exists(filepath) and not overwrite:
                    results.append(AudioJobResult(index=idx, filename=filepath, skipped=True))
                    continue

                futures.append(
                    executor.submit(
                        self._render_item,
                        item,
                        idx,
                        output_dir,
                        filename_key,
                        prefix,
                        overwrite,
                        folder_prefix,
                        filepath=filepath,
                        filename=filename,
                    )
                )
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())
        return results

    def _compute_audio_filename(
        self,
        item: dict,
        index: int,
        output_dir: str,
        filename_key: str,
        prefix: str,
        folder_prefix: str,
    ) -> tuple[str, str]:
        raw_label = item.get(filename_key, f"item{index}")
        label_source = str(raw_label).strip().lower()
        first_word = re.search(r"[a-z0-9]+", label_source)
        if first_word:
            label = first_word.group(0)
        else:
            label = sanitize_filename(label_source)
        prefix_fragment = f"{folder_prefix}_" if folder_prefix else ""
        filename = f"{prefix_fragment}{prefix}_{index}_{label}.mp3"
        filepath = os.path.join(output_dir, filename)
        return filepath, filename


def generate_tts_audio_from_file(
    input_json_path,
    output_dir=None,
    *,
    base_output_dir="output",
    prefix="capability",
    filename_key="capability",
    voice="ash",
    model="tts-1",
    api_key=None,
    overwrite: bool = False,
    max_workers: int = 4,
):
    """Load capability scripts from JSON and generate MP3 files using OpenAI TTS."""

    scripts = safe_load_json(input_json_path)
    if not isinstance(scripts, list):
        print(f"⚠️ Expected a list in {input_json_path}, got {type(scripts)} instead.")
        return []

    if output_dir is None:
        base_name = os.path.basename(os.path.dirname(input_json_path))
        output_dir = os.path.join(base_output_dir, base_name, "audio_files")

    folder_prefix = _resolve_folder_prefix(input_json_path, output_dir)

    try:
        generator = AudioGenerator(api_key=api_key, voice=voice, model=model)
    except ValueError as exc:
        print(f"❌ {exc}")
        return []

    results = generator.generate_from_items(
        scripts,
        output_dir,
        prefix=prefix,
        filename_key=filename_key,
        overwrite=overwrite,
        max_workers=max_workers,
        folder_prefix=folder_prefix,
    )
    for res in results:
        if res.error:
            print(f"❌ Error generating {res.filename or res.index}: {res.error}")
        elif res.skipped:
            print(f"⏩ Skipped existing {res.filename or res.index}")
        else:
            print(f"✅ Saved: {res.filename}")
    return results


# -----------------------------
# Example usage (for manual testing only)
# -----------------------------
# if __name__ == "__main__":
#     try:
#         generate_tts_audio_from_file(
#             "sample_output/capability_scripts.json",
#             "sample_output/audio_files/",
#         )
#     except FileNotFoundError:
#         print("⚠️ Test skipped: sample_output/capability_scripts.json not found.")
