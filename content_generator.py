from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import hashlib
import os
import json
import logging
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def setup_logger(log_file="llm_chain.log", level=logging.INFO):
    logger = logging.getLogger("LLMChainLogger")
    logger.setLevel(level)

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)

    return logger


logger = setup_logger()
logger.setLevel(logging.DEBUG)


# ---------- Typed helpers ----------
@dataclass
class LLMResult:
    content: Any
    raw: str
    is_json: bool
    source: str = "live"


@dataclass
class PromptCache:
    path: Path
    _cached_mtime: Optional[float] = None
    _cached_prompts: Dict[str, str] = field(default_factory=dict)

    def load(self) -> Dict[str, str]:
        if not self.path.exists():
            raise FileNotFoundError(f"Prompts file not found at {self.path}")

        mtime = self.path.stat().st_mtime
        if self._cached_prompts and self._cached_mtime == mtime:
            return self._cached_prompts

        loaded = load_prompts_from_markdown(self.path)
        self._cached_prompts = loaded
        self._cached_mtime = mtime
        return loaded


@dataclass
class OutputPaths:
    base_path: Path

    @classmethod
    def for_user(cls, user_inputs: Dict[str, Any], output_dir: str = "output") -> "OutputPaths":
        sanitized = sanitize_filename(user_inputs.get("folder_path") or user_inputs.get("name"))
        base = Path(output_dir) / sanitized
        base.mkdir(parents=True, exist_ok=True)
        user_inputs["folder_path"] = sanitized
        return cls(base)

    def section_path(self, section: str) -> Path:
        return self.base_path / f"{section}.json"

    def load_json(self, path: Path) -> Optional[Any]:
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to read %s: %s", path, exc)
            return None

    def write_json_if_changed(self, section: str, content: Any) -> Path:
        target = self.section_path(section)
        serialized = json.dumps(content, ensure_ascii=False, indent=2)
        new_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        existing = self.load_json(target)
        if existing is not None:
            existing_hash = hashlib.sha256(
                json.dumps(existing, ensure_ascii=False, indent=2).encode("utf-8")
            ).hexdigest()
            if existing_hash == new_hash:
                logger.info("Skipping write for %s; content unchanged", section)
                return target
        with target.open("w", encoding="utf-8") as handle:
            handle.write(serialized)
        return target


class SafeDict(dict):
    def __missing__(self, key):
        return ""


class ContentPipeline:
    def __init__(
        self,
        prompts_path: Path = Path("prompts.md"),
        output_dir: str = "output",
        *,
        openai_api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> None:
        self.prompts_path = Path(prompts_path)
        self.prompt_cache = PromptCache(self.prompts_path)
        self.output_dir = output_dir
        self.openai_api_key = openai_api_key
        self.model = model
        self.temperature = temperature
        self.llm_client = None

    def _ensure_prompts(self) -> Dict[str, str]:
        return self.prompt_cache.load()

    def _ensure_llm(self):
        global llm
        llm_client = refresh_llm(
            openai_api_key=self.openai_api_key,
            model=self.model,
            temperature=self.temperature,
        )
        self.llm_client = llm_client
        llm = llm_client
        return llm_client

    def _fill_prompt(self, template: str, context: Dict[str, Any]) -> str:
        return template.format_map(SafeDict(context))

    def run_llm(self, prompt_name: str, context: Dict[str, Any], *, expect_json: bool = False) -> LLMResult:
        prompts = self._ensure_prompts()
        template = prompts.get(prompt_name)
        if not template:
            raise ValueError(f"Prompt '{prompt_name}' not found in prompts.md")
        prompt_filled = self._fill_prompt(template, context)
        logger.debug("Prompt (%s): %s", prompt_name, prompt_filled)

        client = self.llm_client or self._ensure_llm()
        if not client:
            simulated = f"Simulated output for {prompt_name}"
            return LLMResult(content=simulated, raw=simulated, is_json=False, source="simulated")

        result = client.invoke(prompt_filled)
        result_text = getattr(result, "content", str(result))
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", result_text, flags=re.IGNORECASE).strip()
        if expect_json:
            try:
                parsed = json.loads(cleaned)
                return LLMResult(content=parsed, raw=result_text, is_json=True)
            except json.JSONDecodeError:
                logger.warning("Expected JSON from %s but got text; returning cleaned text", prompt_name)
        return LLMResult(content=cleaned, raw=result_text, is_json=False)

    def run_pipeline(self, values: dict) -> dict:
        base_context = {"user_input": values.copy(), "_diagnostics": []}
        user_name = base_context["user_input"].get("name")
        if not user_name or not str(user_name).strip():
            raise ValueError("Please provide a non-empty 'name' before running the pipeline.")

        paths = OutputPaths.for_user(base_context["user_input"], output_dir=self.output_dir)
        global llm
        llm = self._ensure_llm()
        base_context["_runtime"] = runtime_summary(base_context["user_input"], output_dir=self.output_dir)

        save_section_to_json(base_context, "user_input", base_context["user_input"], base_path=str(paths.base_path))

        cached_sections, cache_errors = detect_cached_sections(str(paths.base_path), SECTION_SEQUENCE)
        if cache_errors:
            base_context["_diagnostics"].extend(cache_errors)

        context = {"user_input": base_context["user_input"].copy()}

        prompts_map = self._ensure_prompts()
        ai_capability_model = prompts_map.get("ai_capability_model")
        if ai_capability_model:
            context["ai_capability_model"] = ai_capability_model
            logger.info(
                "[INFO] Loaded AI Capability Model context (%d chars) for prompt filling",
                len(ai_capability_model),
            )
        else:
            logger.warning("[WARN] AI Capability Model prompt section missing; context will be blank")

        # Sections that should always be parsed/validated as JSON.
        json_sections = {
            "audience_description",
            "fictional_profile",
            "capability_scripts",
            "capability_use_cases",
        }

        def use_or_generate(section: str, *, expect_json: bool = False):
            cached_value = cached_sections.get(section)
            if cached_value is not None:
                # If a previous run saved the raw JSON string (instead of a parsed
                # object), attempt to parse and heal it so downstream consumers
                # receive structured data rather than an escaped blob.
                if expect_json and isinstance(cached_value, str):
                    try:
                        cached_value = json.loads(cached_value)
                        cached_sections[section] = cached_value
                        paths.write_json_if_changed(section, cached_value)
                        logger.info("Healed cached JSON string for %s", section)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Cached %s JSON was a raw string and could not be parsed; regenerating",
                            section,
                        )
                        cached_value = None

            if cached_value is not None:
                logger.info("Using cached %s from %s", section, paths.base_path)
                return cached_value

            logger.info(
                "[INFO] Generating %s (expect_json=%s). Context keys: %s",
                section,
                expect_json,
                sorted(context.keys()),
            )
            result = self.run_llm(section, context, expect_json=expect_json)
            content = result.content
            paths.write_json_if_changed(section, content)
            return content

        bio = base_context["user_input"].get("bio") or cached_sections.get("bio")
        if bio is None:
            bio_res = use_or_generate("bio")
            bio_text = ensure_text(bio_res)
            base_context["bio"] = bio_text
            base_context["user_input"]["bio"] = bio_text
            paths.write_json_if_changed("bio", bio_text)
        else:
            base_context["bio"] = ensure_text(bio)
            base_context["user_input"]["bio"] = base_context["bio"]

        context["bio"] = base_context["bio"]

        for section in ["audience_description", "fictional_profile", "capability_scripts", "capability_use_cases"]:
            try:
                output = use_or_generate(section, expect_json=section in json_sections)
                base_context[section] = output
                context[section] = output
            except Exception as exc:
                message = f"Error in {section}: {exc}"
                base_context.setdefault("_diagnostics", []).append(message)
                logger.error(message)

        combine_saved_outputs(base_context, SECTION_SEQUENCE, base_path=str(paths.base_path))
        return base_context

# ---------- Prompt loading ----------
def load_prompts_from_markdown(file_path):
    """
    Expect prompts file with headings using '### key_name' and body text below.
    Returns dict: {key_name: prompt_text}
    """
    sections = {}
    current_key = None
    current_lines = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("### "):
                if current_key:
                    sections[current_key] = "".join(current_lines).strip()
                current_key = line.replace("### ", "").strip().lower().replace(" ", "_")
                current_lines = []
            else:
                current_lines.append(line)
        if current_key:
            sections[current_key] = "".join(current_lines).strip()
    return sections


# === Config Profiles ===
config_profiles = {
    "default": {
        "model": "gpt-4-turbo",
        "temperature": 0.2
    },
    "creative": {
        "model": "gpt-4-turbo",
        "temperature": 0.8
    },
    "fast": {
        "model": "gpt-3.5-turbo",
        "temperature": 0.5
    }
}

# Use default config for now
current_config = config_profiles["default"]

config = {
    "model": current_config["model"],
    "temperature": current_config["temperature"],
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "serpapi_key": os.getenv("SERPAPI_KEY"),
    "engine": "google"
}

def get_llm(config):
    return ChatOpenAI(
        openai_api_key=config["openai_api_key"],
        model=config["model"],
        temperature=config["temperature"]
    )


def refresh_llm(openai_api_key=None, model=None, temperature=None):
    """
    Resolve configuration from environment or explicit overrides and build
    a ChatOpenAI client. This is re-run at pipeline start so the notebook can
    set environment variables *after* importing the module.
    """

    config["openai_api_key"] = openai_api_key or os.getenv("OPENAI_API_KEY")
    config["model"] = model or config["model"]
    config["temperature"] = temperature if temperature is not None else config["temperature"]

    if not config["openai_api_key"]:
        logger.warning(
            "OPENAI_API_KEY is not set. Falling back to simulated outputs for all LLM calls."
        )
        return None

    try:
        return get_llm(config)
    except Exception as exc:
        logger.error(f"Failed to initialize ChatOpenAI client: {exc}")
        return None


def _mask_key(key):
    """Return a short, non-sensitive fingerprint of a secret for diagnostics."""
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def runtime_summary(values, output_dir="output"):
    """Collect a concise snapshot of key runtime settings for troubleshooting."""
    name = values.get("name") or "anonymous"
    name_sanitized = sanitize_filename(name)
    folder_path = values.get("folder_path") or name_sanitized
    return {
        "openai_api_key_detected": bool(config.get("openai_api_key")),
        "openai_client_initialized": llm is not None,
        "openai_api_key_fingerprint": _mask_key(config.get("openai_api_key")),
        "model": config.get("model"),
        "temperature": config.get("temperature"),
        "output_folder": os.path.abspath(os.path.join(output_dir, folder_path)),
    }


# llm is refreshed on-demand at pipeline start
llm = None


# ==========================================================
# ---------- Prompt execution ----------
# ==========================================================
prompts = load_prompts_from_markdown("prompts.md")

# Shared list of pipeline sections to keep load/save logic centralized.
SECTION_SEQUENCE = [
    "bio",
    "audience_description",
    "fictional_profile",
    "capability_scripts",
    "capability_use_cases",
]

# Sections that are allowed to live inside user_input.json instead of a
# standalone <section>.json. These should still be considered "present" for
# cache validation as long as the field exists in user_input.json.
INLINE_SECTION_SOURCES = {"bio"}

def run_llm(prompt_name, context, llm_client=None):
    """
    Run prompt and return either:
      - parsed JSON (dict/list) if the model returned JSON, or
      - cleaned plain string otherwise.
    """
    template = prompts.get(prompt_name)
    if not template:
        raise ValueError(f"Prompt '{prompt_name}' not found in prompts.md")


    # Ensure the AI Capability Model is available to templates expecting it
    ai_capability_context = context.get("ai_capability_model") or prompts.get(
        "ai_capability_model", ""
    )
    if ai_capability_context:
        logger.info(
            "[INFO] Module run_llm using AI Capability Model context (%d chars)",
            len(ai_capability_context),
        )
    else:
        logger.warning(
            "[WARN] Module run_llm missing AI Capability Model context; prompt may be incomplete"
        )

    context = {**context, "ai_capability_model": ai_capability_context}

    # Fill placeholders (keep your existing formatting logic)
    prompt_filled = template.format(**context)
    logger.debug("Prompt (%s): %s", prompt_name, prompt_filled)

    client = llm_client or llm
    if not client:
        # simulation mode -> return a simple string
        logger.warning(
            "Simulating output for '%s' because no OpenAI client is configured.",
            prompt_name,
        )
        return f"Simulated output for {prompt_name}"

    # call LLM (keep whatever call you use; example uses llm.invoke)
    result = client.invoke(prompt_filled)           # may return AIMessage or string
    result_text = getattr(result, "content", str(result))

    # --- CLEAN UP: remove code fences anywhere (```json ... ``` or ``` ... ```)
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", result_text, flags=re.IGNORECASE).strip()

    # Try to parse JSON inside the cleaned string
    try:
        parsed = json.loads(cleaned)
        logger.debug("Parsed JSON from LLM for %s", prompt_name)
        return parsed   # dict or list
    except json.JSONDecodeError:
        # Not JSON — return cleaned text string
        logger.debug("LLM output not JSON for %s; returning cleaned text", prompt_name)
        return cleaned


# ==========================================================
# ---------- Sequential LLM pipeline ----------
# ==========================================================
def run_pipeline(values: dict, *, openai_api_key=None, model=None, temperature=None):
    pipeline = ContentPipeline(
        prompts_path=Path("prompts.md"),
        output_dir="output",
        openai_api_key=openai_api_key,
        model=model,
        temperature=temperature,
    )
    return pipeline.run_pipeline(values)



# === Utility Functions ===
def sanitize_filename(name, default="anonymous"):
    """
    Normalize a name for safe folder/file usage while tolerating None or
    non-string inputs. Any sanitization failure falls back to the provided
    default to prevent TypeErrors mid-pipeline.
    """
    try:
        if not name:
            return default
        if not isinstance(name, str):
            name = str(name)
        return re.sub(r'\W+', '_', name).strip('_').lower() or default
    except Exception as exc:
        logger.warning("Failed to sanitize name %r: %s; using %s", name, exc, default)
        return default

def ensure_string(value):
    if isinstance(value, list):
        return str(value[0]) if value else "unknown"
    return str(value)

def clean_json_output(output):
    output = re.sub(r"^```(?:json)?|```$", "", output.strip(), flags=re.MULTILINE)
    output = re.sub(r'[^\x20-\x7E\n\r]', '', output)
    return output.strip()


def resolve_output_folder(user_inputs, output_dir="output"):
    """
    Determine the output folder to use for this run, honoring an explicit
    folder_path when provided and persisting it back to user_inputs so the
    notebook writes it into user_input.json.
    """
    if not isinstance(user_inputs, dict):
        user_inputs = {}

    folder_raw = user_inputs.get("folder_path")
    folder_sanitized = sanitize_filename(folder_raw, default="") if folder_raw else ""

    if not folder_sanitized:
        folder_sanitized = sanitize_filename(user_inputs.get("name"))

    if not folder_sanitized:
        folder_sanitized = "anonymous"

    base_path = os.path.join(output_dir, folder_sanitized)
    os.makedirs(base_path, exist_ok=True)

    # Persist the resolved path back into user_inputs so downstream consumers
    # (and user_input.json) can see the chosen folder.
    user_inputs["folder_path"] = folder_sanitized
    return base_path


def load_json_if_valid(path):
    """Load a JSON file if it exists and contains valid JSON."""
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in {path}: {exc}"
    except Exception as exc:  # pragma: no cover - defensive logging
        return None, f"Unexpected error reading {path}: {exc}"


def _load_user_input_from_folder(base_path):
    """Best-effort load of user_input.json for inline section validation."""
    user_input_path = os.path.join(base_path, "user_input.json")
    return load_json_if_valid(user_input_path)


def detect_cached_sections(base_path, section_names, inline_sections=INLINE_SECTION_SOURCES):
    """
    Inspect the output folder for any valid JSON sections and return a tuple of
    (cached_sections, errors). Cached sections may be partial; callers decide
    whether to regenerate missing entries.
    """
    user_input, user_input_error = _load_user_input_from_folder(base_path)
    cached = {}
    errors = []
    if user_input_error:
        errors.append(user_input_error)
    if user_input is not None:
        cached["user_input"] = user_input

    for section in section_names:
        candidate = os.path.join(base_path, f"{section}.json")
        data, error = load_json_if_valid(candidate)
        if data is not None:
            cached[section] = data
        elif section in inline_sections and user_input and section in user_input:
            cached[section] = user_input.get(section)
        elif error:
            errors.append(error)
    return cached, errors


# === File I/O ===
def save_section_to_json(context, section_name, content, output_dir="output", base_path=None):

# 1️⃣ Determine user folder path
    if base_path is None:
        user_name = context.get("user_input", {}).get("name") or context.get("name", "anonymous")
        name_sanitized = sanitize_filename(user_name)
        base_path = os.path.join(output_dir, name_sanitized)
    os.makedirs(base_path, exist_ok=True)

    # 2️⃣ Determine final save path
    file_path = os.path.join(base_path, f"{section_name}.json")

    # --- Clean and prepare content ---
    try:
        if isinstance(content, str):
            cleaned = clean_json_output(content)
            # Try to parse JSON text if possible
            try:
                content_json = json.loads(cleaned)
            except json.JSONDecodeError:
                content_json = {"text": cleaned}
        elif isinstance(content, (dict, list)):
            content_json = content
        else:
            # Convert unknown objects to string
            content_json = {"text": str(content)}
    except Exception as e:
        logger.error(f"Error preparing content for JSON: {e}")
        content_json = {"text": str(content)}

        # 4️⃣ Write to file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content_json, f, indent=2, ensure_ascii=False)
        logger.info(f"[INFO] Saved '{section_name}' to {file_path}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to write JSON file for {section_name}: {e}")

    return file_path


def ensure_text(result):
    """
    Accepts whatever run_llm returned and returns a plain string.
    - If result is string -> return it
    - If dict/list -> try to extract likely text fields, or json.dumps it
    """
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        # common patterns: {"text": "..."} or {"result": "..."}
        if "text" in result and isinstance(result["text"], str):
            return result["text"]
        if "result" in result and isinstance(result["result"], str):
            return result["result"]
        # otherwise stringify dict to preserve structure
        return json.dumps(result, ensure_ascii=False, indent=2)
    if isinstance(result, list):
        # join or dump list as string
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)

# === Combine Output Sections ===
def _resolve_user_folder(context, output_dir="output", base_path=None):
    """Return the per-user folder path, honoring folder_path when available."""
    if base_path:
        os.makedirs(base_path, exist_ok=True)
        return base_path

    if not isinstance(context, dict):
        logger.warning("Context missing or invalid when resolving user folder; using anonymous")
        name = "anonymous"
        folder = None
    else:
        folder = (
            sanitize_filename(context.get("folder_path"))
            or sanitize_filename(context.get("user_input", {}).get("folder_path"))
        )
        name = (
            sanitize_filename(context.get("name"))
            or sanitize_filename(context.get("user_input", {}).get("name"))
        )

    final_folder = folder or name or "anonymous"

    base_path = os.path.join(output_dir, final_folder)
    os.makedirs(base_path, exist_ok=True)
    return base_path


def validate_saved_sections(base_path, section_names, inline_sections=INLINE_SECTION_SOURCES):
    """
    Raise a clear error if any expected JSON files are missing.

    Sections listed in ``inline_sections`` may be satisfied by fields inside
    user_input.json (for example, ``bio`` is supplied by the user input form and
    may never be persisted as a standalone bio.json). This keeps validation
    aligned with how the pipeline actually stores data.
    """

    resolved_base = Path(_resolve_user_folder({}, base_path=base_path))
    user_input, user_input_error = _load_user_input_from_folder(resolved_base)
    missing = []

    for section in section_names:
        candidate = resolved_base / f"{section}.json"
        if candidate.exists():
            continue

        if section in inline_sections and user_input and section in user_input:
            continue

        missing.append(section)

    if missing:
        details = ", ".join(missing)
        hint = ""
        if user_input_error:
            hint = f" (note: user_input.json error: {user_input_error})"
        raise FileNotFoundError(
            f"Missing required JSON sections in {resolved_base}: {details}{hint}"
        )


def combine_saved_outputs(context, section_names, output_dir="output", output_filename="combined_output.json", base_path=None):
    """
    Combines all saved JSON sections into a single combined_output.json file.
    Respects per-user folder structure (output/<name>/combined_output.json).
    """
    base_path = _resolve_user_folder(context, output_dir, base_path)

    combined = context.copy() if isinstance(context, dict) else {}

    # ✅ Load each section from *within the user folder*
    for section in section_names:
        section_path = os.path.join(base_path, f"{section}.json")
        try:
            with open(section_path, "r", encoding="utf-8") as f:
                combined[section] = json.load(f)
                logger.info(f"Loaded section '{section}' from {section_path}")
        except FileNotFoundError:
            logger.warning(f"{section}.json not found at {section_path}. Skipping.")
        except json.JSONDecodeError:
            logger.error(f"{section}.json is not valid JSON. Skipping.")
        except Exception as e:
            logger.error(f"Unexpected error loading {section}: {e}")

    # ✅ Write combined output inside same folder
    combined_path = os.path.join(base_path, output_filename)
    try:
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(combined, f, indent=2, ensure_ascii=False)
        logger.info(f"\nCombined output saved to {combined_path}")
    except Exception as exc:
        logger.error(f"Failed to write combined output to {combined_path}: {exc}")
    return combined_path


if __name__ == "__main__":
    sample_values = {
        "name": "Chelsey Engerran-Singh",
        "gender": "Female",
        "title": "Activities & Volunteer Coordinator",
        "company": "Sunrise Senior Living",
        "bio": "",
        "notes": "Interested in AI automation for sales workflows."
    }

    run_pipeline(sample_values)

    