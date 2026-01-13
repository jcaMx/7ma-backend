# slide-updater.py
import re
import os
import json
import logging
from functools import lru_cache
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------- Config / logging ----------
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("slide-updater")

slide_map = [
    {
        "label": "fictional_profile",
        "position": 3, #slide 3
        "source": "fictional_profile",
        "field_map": {0: "narrative", 1: "name", 2: "role"}
    },
    {
        "label": "capability_inform",
        "position": 5, #slide 5
        "source": None,
        "field_map": {1: "name", 2: "audio"}
    },
    {
        "label": "capability_scenario_inform",
        "position": 6, #slide 6
        "source": {"collection": "capability_use_cases", "match": {"capability": "Inform"}},
        "field_map": {0: "name", 1: "scenario", 2: "solution"}
    },
    {
        "label": "capability_create",
        "position": "capability_inform + 2",
        "source": None,
        "field_map": {1: "name", 2: "audio"},
        "add_audio": True
    },
    {
        "label": "capability_scenario_create",
        "position": "capability_scenario_inform + 2",
        "source": {"collection": "capability_use_cases", "match": {"capability": "Create & Edit"}},
        "field_map": {0: "scenario", 1: "solution", 2: "name"}
    },
    {
        "label": "capability_organize",
        "position": "capability_create + 2",
        "source": None,
        "field_map": {1: "name", 2: "audio"},
        "add_audio": True
    },
    {
        "label": "capability_scenario_organize",
        "position": "capability_scenario_create + 2",
        "source": {"collection": "capability_use_cases", "match": {"capability": "Organize"}},
        "field_map": {0: "scenario", 1: "solution", 2: "name"}
    },
    {
        "label": "capability_transform",
        "position": "capability_organize + 2",
        "source": None,
        "field_map": {1: "name", 2: "audio"},
        "add_audio": True
    },
    {
        "label": "capability_scenario_transform",
        "position": "capability_scenario_organize + 2",
        "source": {"collection": "capability_use_cases", "match": {"capability": "Transform"}},
        "field_map": {0: "scenario", 1: "solution", 2: "name"}
    },
    {
        "label": "capability_analyze",
        "position": "capability_transform + 2",
        "source": None,
        "field_map": {1: "name", 2: "audio"},
        "add_audio": True
    },
    {
        "label": "capability_scenario_analyze",
        "position": "capability_scenario_transform + 2",
        "source": {"collection": "capability_use_cases", "match": {"capability": "Analyze"}},
        "field_map": {0: "scenario", 1: "solution", 2: "name"}
    },
    {
        "label": "capability_personify",
        "position": "capability_analyze + 2",
        "source": None,
        "field_map": {1: "name", 2: "audio"},
        "add_audio": True
    },
    {
        "label": "capability_scenario_personify",
        "position": "capability_scenario_analyze + 2",
        "source": {"collection": "capability_use_cases", "match": {"capability": "Personify or Simulate"}},
        "field_map": {0: "scenario", 1: "solution", 2: "name"}
    },
    {
        "label": "capability_explore",
        "position": "capability_personify + 2",
        "source": None,
        "field_map": {1: "name", 2: "audio"},
        "add_audio": True
    },
    {
        "label": "capability_scenario_explore",
        "position": "capability_scenario_personify + 2",
        "source": {"collection": "capability_use_cases", "match": {"capability": "Explore & Guide"}},
        "field_map": {0: "name", 1: "scenario", 2: "solution"}
    }
]


# --- Authentication Setup ---
SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive"
]
SERVICE_ACCOUNT_FILE = "credentials.json"
SHARED_DRIVE_ID = os.getenv("SHARED_DRIVE_ID")
SHARED_DRIVE_FOLDER_ID = os.getenv(
    "SHARED_DRIVE_FOLDER_ID")


@lru_cache(maxsize=1)
def get_services(credentials_file: str = SERVICE_ACCOUNT_FILE):
    """Lazily create and cache Slides/Drive service clients."""
    credentials = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=SCOPES
    )
    slides = build("slides", "v1", credentials=credentials)
    drive = build("drive", "v3", credentials=credentials)
    return slides, drive

# ---------- Helpers ----------
def interpolate(template: str, data: dict) -> str:
    """Replace {{key}} occurrences with data[key] values (if present)."""
    if template is None:
        return ""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(data.get(m.group(1), "")), template)

def resolve_positions(slide_map):
    """Resolve label -> zero-based slide index. Supports 'label + N' style relative positions."""
    label_to_position = {}
    for item in slide_map:
        pos = item["position"]
        if isinstance(pos, int):
            label_to_position[item["label"]] = pos - 1
        elif isinstance(pos, str) and "+" in pos:
            base_label, offset = pos.split("+")
            base_label = base_label.strip()
            offset = int(offset.strip())
            if base_label not in label_to_position:
                raise KeyError(f"Base label '{base_label}' not resolved yet for {item['label']}")
            label_to_position[item["label"]] = label_to_position[base_label] + offset
        else:
            raise ValueError(f"Invalid position for label {item['label']}: {pos}")
    return label_to_position


def _sanitize_filename(value: str) -> str:
    """Safe, predictable filename fragments."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value.strip())


def _infer_audio_prefix(audio_dir: str, content_dict: dict) -> str:
    """Use folder_path when available so audio files remain unique across users."""
    if isinstance(content_dict, dict):
        user_input = content_dict.get("user_input") or {}
        folder = user_input.get("folder_path") or user_input.get("name")
        if folder:
            return _sanitize_filename(str(folder))

    if audio_dir:
        # expect .../<folder>/audio_files
        parent = os.path.basename(os.path.dirname(os.path.abspath(audio_dir)))
        if parent:
            return _sanitize_filename(parent)

    return ""

def resolve_content(source_def, content_dict):
    """
    Return content resolved from content_dict according to source_def.
    - If source_def is None => returns {} (no content)
    - If source_def is a string => return content_dict[source_def] or {}
    - If source_def is a dict with 'collection' and 'match' => search collection,
      compare keys case-insensitively and strip whitespace.
    """
    if source_def is None:
        return {}

    if isinstance(source_def, str):
        return content_dict.get(source_def, {})

    if isinstance(source_def, dict):
        collection_name = source_def.get("collection")
        match = source_def.get("match", {})
        collection = content_dict.get(collection_name, [])
        # tolerant matching: lower+strip
        def matches(item, match):
            for k, v in match.items():
                item_val = str(item.get(k, "")).strip().lower()
                match_val = str(v).strip().lower()
                if item_val != match_val:
                    return False
            return True

        for itm in collection:
            if matches(itm, match):
                return itm

        # debug: print available values if no match
        available = [ {k: itm.get(k) for k in match.keys()} for itm in collection ]
        print(f"⚠️ resolve_content: no match for {match} in collection '{collection_name}'. Available samples: {available}")
        return {}

    return {}


def fetch_presentation(slides_service, presentation_id: str):
    """Fetch presentation once and return the full object."""
    return slides_service.presentations().get(presentationId=presentation_id).execute()


def _presentation_url(presentation_id: str) -> str:
    return f"https://docs.google.com/presentation/d/{presentation_id}/preview"


def _format_copy_name(user_inputs: Optional[dict], source_name: Optional[str]) -> str:
    """Derive a copy name using the 7MA convention and fall back sensibly."""

    title = ""
    company = ""
    if isinstance(user_inputs, dict):
        title = str(user_inputs.get("title", "")).strip()
        company = str(user_inputs.get("company", "")).strip()

    if title or company:
        title_part = title or "Untitled"
        company_part = company or "Company"
        return f"7MA - {title_part} - {company_part}"

    if source_name:
        return f"{source_name} (Copy)"

    return "7MA - Untitled - Company"


def _prepare_presentation_id(
    drive_service,
    presentation_id: str,
    *,
    create_new_presentation: bool = False,
    user_inputs: Optional[dict] = None,
) -> str:
    """Optionally copy the presentation and return the ID to update."""

    if not create_new_presentation:
        return presentation_id

    parents = []
    source_name = None
    try:
        metadata = (
            drive_service.files()
            .get(
                fileId=presentation_id,
                fields="id,name,parents",
                supportsAllDrives=True,
            )
            .execute()
        )
        parents = metadata.get("parents", []) or []
        source_name = metadata.get("name")
    except Exception as exc:
        logger.warning(
            "Could not fetch presentation metadata for %s; proceeding without parents: %s",
            presentation_id,
            exc,
        )

    copy_name = _format_copy_name(user_inputs, source_name)
    copy_body = {"name": copy_name}
    if parents:
        copy_body["parents"] = parents

    try:
        copied = (
            drive_service.files()
            .copy(
                fileId=presentation_id,
                body=copy_body,
                supportsAllDrives=True,
                fields="id,name,parents",
            )
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to copy presentation %s: %s", presentation_id, exc)
        raise

    new_id = copied.get("id")
    logger.info(
        "Created presentation copy '%s' (source: %s) -> new id %s",
        copy_name,
        presentation_id,
        new_id,
    )
    return new_id


def preindex_text_boxes(presentation):
    """Return mapping of slide ID -> list of text box elements for faster lookup."""
    index = {}
    for slide in presentation.get("slides", []):
        slide_id = slide.get("objectId")
        if not slide_id:
            continue
        shapes = []
        for page_element in slide.get("pageElements", []):
            shape = page_element.get("shape")
            if shape and "text" in shape:
                shapes.append(page_element)
        index[slide_id] = shapes
    return index


def _get_text_from_shape(shape_obj):
    """Extract concatenated text from a Slides 'shape' object (which contains 'text')."""
    if not shape_obj or not isinstance(shape_obj, dict):
        return ""
    text = ""
    for te in shape_obj.get("text", {}).get("textElements", []):
        if "textRun" in te:
            text += te["textRun"].get("content", "")
    return text

def _upload_file_to_drive(
    drive_service,
    local_path,
    name=None,
    mime_type="audio/mpeg",
    *,
    drive_id: str | None = None,
    parent_folder_id: str | None = None,
):
    """
    Upload a local file to Drive and return its file id.

    When using a service account, uploads should target a shared drive because
    personal Drive storage quotas are unavailable. Configure one of the
    following environment variables so uploads land in a shared drive the
    service account can access:

    - ``SHARED_DRIVE_ID``: uploads to the shared drive root
    - ``SHARED_DRIVE_FOLDER_ID``: uploads to a folder within the shared drive
    """

    name = name or os.path.basename(local_path)
    media = MediaFileUpload(local_path, mimetype=mime_type)
    metadata = {"name": name}

    parent = parent_folder_id or drive_id
    if parent:
        metadata["parents"] = [parent]

    supports_drives = bool(parent)
    file = (
        drive_service
        .files()
        .create(
            body=metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=supports_drives,
        )
        .execute()
    )
    return file.get("id")

# ---------- Main update function ----------
def update_slide_text_fields(
    *,
    slides_service,
    drive_service,
    presentation_id,
    jsondata,
    field_map,
    slide,
    audio_dir=None,
    audio_index=None,
    label=None,
    add_audio=False,
    presentation=None,
    audio_prefix: str = "",
):
    """
    Updates text fields on a given slide and optionally inserts audio.
    - jsondata: dict used to fetch replacement values (jsondata.get(field, ""))
    - field_map: {index: "key_in_jsondata"} mapping to text boxes ordered visually
    - slide: zero-based slide index
    - audio_dir, audio_index, add_audio: used to upload/insert audio when True
    """

    if presentation is None:
        presentation = slides_service.presentations().get(
            presentationId=presentation_id
        ).execute()
    slides = presentation.get('slides', [])

    # Debug: print slide map summary
    # print("\n========== SLIDE STRUCTURE DEBUG ==========")
    # for i, s in enumerate(slides):
    #     print(f"UI Position {i + 1:02d} → API ID: {s.get('objectId')} | Elements: {len(s.get('pageElements', []))}")
    # print("===========================================\n")

    if not isinstance(slide, int) or slide < 0 or slide >= len(slides):
        raise IndexError(f"Slide index {slide} is out of range. Presentation has {len(slides)} slides.")

    target_slide = slides[slide]
    print(f"\n🔍 Inspecting slide {slide + 1} (Object ID: {target_slide.get('objectId')})")

    # --- Enumerate all elements and print debug info (ID, type, text) ---
    print("   --- Elements on slide ---")
    for el in target_slide.get('pageElements', []):
        eid = el.get('objectId')
        # robust type detection
        etype = "UNKNOWN"
        if "shape" in el and isinstance(el["shape"], dict):
            etype = el["shape"].get("shapeType", "UNKNOWN")
        elif "video" in el:
            etype = "VIDEO"
        elif "image" in el:
            etype = "IMAGE"
        elif "table" in el:
            etype = "TABLE"
        text_content = ""
        if "shape" in el and isinstance(el["shape"], dict) and "text" in el["shape"]:
            text_content = _get_text_from_shape(el["shape"])
        print(f"   → ID: {eid}, Type: {etype}, Text: '{text_content}'")

    # --- Collect text boxes (store whole shape object so we can get existing text) ---
    text_shapes = []
    audio_shapes = []
    for el in target_slide.get('pageElements', []):
        if "shape" in el and isinstance(el["shape"], dict) and el["shape"].get("shapeType") == "TEXT_BOX":
            transform = el.get('transform', {})
            text_shapes.append({
                'objectId': el['objectId'],
                'shape': el['shape'],      # keep the whole shape object
                'left': transform.get('translateX', 0),
                'top': transform.get('translateY', 0)
            })
        # detect audio/video placeholders (some templates use video placeholders)
        if "video" in el or "audio" in el:
            audio_shapes.append(el)

    print(f"✅ Found {len(text_shapes)} text boxes and {len(audio_shapes)} audio/video elements on slide {slide + 1}.")

    # Safety: continue even if some field_map indexes are missing; report
    if len(text_shapes) == 0:
        print(f"⚠️ No text boxes found on slide {slide + 1}")
        return

    # sort top-to-bottom left-to-right for approximate mapping
    text_shapes.sort(key=lambda x: (round(x['top'] / 10) * 10, x['left']))

    requests = []
    any_replacement = False

    for index, field in field_map.items():
        if index >= len(text_shapes):
            print(f"⚠️ No text shape found for index {index} on slide {slide + 1} — skipping.")
            continue

        object_id = text_shapes[index]['objectId']
        shape_obj = text_shapes[index]['shape']   # your code stores the shape object
        old_text = _get_text_from_shape(shape_obj)
        new_text = str(jsondata.get(field, "")).strip()

        print(f"\n📝 [DEBUG] Field {index} -> '{field}'")
        print(f"    Old text (len={len(old_text)}): '{old_text}'")
        print(f"    New text (len={len(new_text)}): '{new_text}'")

        # If new_text is empty, preserve existing text (do not delete)
        if new_text == "":
            print(f"    ⏭️ Skipping replacement because new text is empty; preserving existing placeholder/text.")
            continue

        # Delete existing content (only if it exists) then insert new text
        if old_text and old_text.strip():
            requests.append({
                'deleteText': {
                    'objectId': object_id,
                    'textRange': {'type': 'ALL'}
                }
            })
        requests.append({
            'insertText': {
                'objectId': object_id,
                'insertionIndex': 0,
                'text': new_text
            }
        })
        any_replacement = True


    # Execute text updates if any
    if any_replacement and requests:
        slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': requests}
        ).execute()
        print(f"✅ Updated text on slide {slide + 1}")
    else:
        print(f"⚠️ No text updates were made for slide {slide + 1}")


    # --- AUDIO: upload / insert if requested ---
    if add_audio and audio_dir:
        # Audio filename scheme: <folder>_capability_<n>_<label_suffix>.mp3
        # audio_index in this refactor is the running count of audio slides (1..N)
        # label suffix is the last token after underscore (e.g. capability_create -> create)
        label_suffix = (label.split("_")[-1] if label else f"slide{slide+1}")
        prefix_fragment = f"{audio_prefix}_" if audio_prefix else ""
        audio_filename = f"{prefix_fragment}capability_{audio_index}_{label_suffix}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)

        if not os.path.exists(audio_path):
            print(f"⚠️ Missing audio file: {audio_filename}")
            return

        print(f"🎧 Uploading & inserting audio '{audio_filename}' to slide {slide + 1}...")

        try:
            # upload audio to Drive
            file_id = _upload_file_to_drive(
                drive_service,
                audio_path,
                name=audio_filename,
                mime_type="audio/mpeg",
                drive_id=SHARED_DRIVE_ID,
                parent_folder_id=SHARED_DRIVE_FOLDER_ID,
            )
            audio_url = f"https://drive.google.com/uc?id={file_id}"

            # Insert as a video element (Play icon) referencing the Drive URL
            create_video_req = {
                "createVideo": {
                    "url": audio_url,
                    "elementProperties": {
                        "pageObjectId": target_slide['objectId'],
                        "size": {"height": {"magnitude": 60, "unit": "PT"},
                                 "width": {"magnitude": 60, "unit": "PT"}},
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": 50,
                            "translateY": 400,
                            "unit": "PT"
                        }
                    }
                }
            }

            slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={"requests": [create_video_req]}
            ).execute()
            print(f"✅ Audio inserted as video element on slide {slide + 1}: {audio_filename}")
        except Exception as e:
            if "storageQuotaExceeded" in str(e):
                print(
                    "❌ Failed to insert audio because the service account has no Drive "
                    "storage. Set SHARED_DRIVE_ID (and optionally SHARED_DRIVE_FOLDER_ID) "
                    "to upload audio into a shared drive accessible to the service account."
                )
            print(f"❌ Failed to insert audio on slide {slide + 1}: {e}")


def update_slides(
    presentation_id,
    slide_map,
    content_dict,
    *,
    audio_dir=None,
    credentials_file: str = SERVICE_ACCOUNT_FILE,
    create_new_presentation: bool = False,
    user_inputs: Optional[dict] = None,
):
    """Top-level loop: resolves slide indexes and updates slides. Handles audio indexing."""

    slides_service, drive_service = get_services(credentials_file)

    effective_user_inputs = user_inputs or content_dict.get("user_input") or {}
    effective_presentation_id = _prepare_presentation_id(
        drive_service,
        presentation_id,
        create_new_presentation=create_new_presentation,
        user_inputs=effective_user_inputs,
    )

    # quick connectivity check to fail fast with a clear message
    try:
        slides_service.presentations().get(
            presentationId=effective_presentation_id
        ).execute()
        logger.info("Google Slides API connection OK")
    except Exception as exc:
        logger.error("Slides API connection failed: %s", exc)
        raise

    positions = resolve_positions(slide_map)

    # build ordered list of items in slide_map so relative positions resolve properly
    # We'll iterate original slide_map order and keep an audio counter for add_audio slides.
    # Audio files start at capability_1_inform (not inserted), so begin counting from 1
    # to align capability_create with capability_2_* filenames generated by audio_generator.
    audio_counter = 1
    audio_prefix = _infer_audio_prefix(audio_dir or "", content_dict)

    for item in slide_map:
        slide_label = item["label"]
        slide_index = positions[slide_label]
        content = resolve_content(item.get("source"), content_dict)
        logger.info("Updating slide '%s' (index %d)", slide_label, slide_index + 1)

        # determine audio index only for slides that need audio
        add_audio = bool(item.get("add_audio", False))
        audio_index = None
        if add_audio:
            audio_counter += 1
            audio_index = audio_counter

        # pass label and audio_index into update function
        update_slide_text_fields(
            slides_service=slides_service,
            drive_service=drive_service,
            presentation_id=effective_presentation_id,
            jsondata=content,
            field_map=item['field_map'],
            slide=slide_index,
            audio_dir=audio_dir,
            audio_index=audio_index,
            label=slide_label,
            add_audio=add_audio,
            audio_prefix=audio_prefix,
        )

    final_url = _presentation_url(effective_presentation_id)
    logger.info("Slides updated at %s", final_url)
    return final_url


def update_slides_prefetched(
    presentation_id,
    slide_map,
    content_dict,
    *,
    audio_dir=None,
    credentials_file: str = SERVICE_ACCOUNT_FILE,
    create_new_presentation: bool = False,
    user_inputs: Optional[dict] = None,
):
    """Fetch the presentation once and reuse indexed slides for updates."""

    slides_service, drive_service = get_services(credentials_file)
    effective_user_inputs = user_inputs or content_dict.get("user_input") or {}
    effective_presentation_id = _prepare_presentation_id(
        drive_service,
        presentation_id,
        create_new_presentation=create_new_presentation,
        user_inputs=effective_user_inputs,
    )
    presentation = fetch_presentation(slides_service, effective_presentation_id)
    positions = resolve_positions(slide_map)

    # Audio files start at capability_1_inform (not inserted), so begin counting from 1
    # to align capability_create with capability_2_* filenames generated by audio_generator.
    audio_counter = 1
    audio_prefix = _infer_audio_prefix(audio_dir or "", content_dict)
    for item in slide_map:
        slide_label = item["label"]
        slide_index = positions[slide_label]
        content = resolve_content(item.get("source"), content_dict)

        add_audio = bool(item.get("add_audio", False))
        audio_index = None
        if add_audio:
            audio_counter += 1
            audio_index = audio_counter

        update_slide_text_fields(
            slides_service=slides_service,
            drive_service=drive_service,
            presentation_id=effective_presentation_id,
            jsondata=content,
            field_map=item['field_map'],
            slide=slide_index,
            audio_dir=audio_dir,
            audio_index=audio_index,
            label=slide_label,
            add_audio=add_audio,
            presentation=presentation,
            audio_prefix=audio_prefix,
        )

    logger.info("Completed slide updates with single presentation fetch.")
    final_url = _presentation_url(effective_presentation_id)
    logger.info("Slides updated at %s", final_url)
    return final_url

# ---------- Manual test block ----------
# Uncomment to run a manual test of slide updates
# if __name__ == "__main__":



    # adjust output_dir to point to the folder with your JSON outputs
    # try:
    #     output_dir = "output/name"
    #     audio_folder = os.path.join(output_dir, "audio_files")
    #     fictional_path = os.path.join(output_dir, "fictional_profile.json")
    #     capabilities_path = os.path.join(output_dir, "capability_use_cases.json")

    #     if not os.path.exists(fictional_path) or not os.path.exists(capabilities_path):
    #         logger.error("Required JSON outputs missing in %s", output_dir)
    #         raise SystemExit(1)

    #     with open(fictional_path, "r", encoding="utf-8") as f:
    #         fictional_data = json.load(f)

    #     with open(capabilities_path, "r", encoding="utf-8") as f:
    #         capability_data = json.load(f)

    #     # Normalize content_dict
    #     content_dict = {
    #         "fictional_profile": {
    #             "name": fictional_data.get("name", ""),
    #             "role": fictional_data.get("role", ""),
    #             "narrative": fictional_data.get("narrative", "")
    #         },
    #         "capability_use_cases": capability_data
    #     }
    #     print("📦 content_dict keys:", content_dict.keys())

    #     # Run updates (pass audio folder if you want audio files inserted)
    #     audio_folder = os.path.join(output_dir, "audio_files")
    #     demo_presentation_id = os.environ.get("PRESENTATION_ID", "")
    #     if not demo_presentation_id:
    #         raise SystemExit("Set PRESENTATION_ID env var to run the manual test block.")
    #     update_slides(demo_presentation_id, slide_map, content_dict, audio_dir=audio_folder)

    #     logger.info("All done.")

    # except Exception as e:
        # logger.error(f"❌ Slide update test failed: {e}")



def inspect_slide_objects(presentation: dict, slide_index: int) -> dict:
    """
    Inspect objects on a single slide.
    - No updates
    - No recursion
    - No API calls
    Returns a structured summary.
    """

    slides = presentation.get("slides", [])
    if slide_index < 0 or slide_index >= len(slides):
        raise IndexError(
            f"Slide index {slide_index} out of range (total slides: {len(slides)})"
        )

    slide = slides[slide_index]
    slide_id = slide.get("objectId")

    print(f"\n🔍 Inspecting slide {slide_index + 1} (Object ID: {slide_id})")
    print(" --- Elements on slide ---")

    summary = {
        "slide_index": slide_index,
        "slide_id": slide_id,
        "elements": [],
    }

    for el in slide.get("pageElements", []):
        element_id = el.get("objectId")
        element_type = "UNKNOWN"
        text_content = ""

        if "shape" in el and isinstance(el["shape"], dict):
            element_type = el["shape"].get("shapeType", "SHAPE")
            if "text" in el["shape"]:
                text_content = _get_text_from_shape(el["shape"])

        elif "image" in el:
            element_type = "IMAGE"

        elif "video" in el:
            element_type = "VIDEO"

        elif "table" in el:
            element_type = "TABLE"

        print(
            f" → ID: {element_id}, "
            f"Type: {element_type}, "
            f"Text: '{text_content}'"
        )

        summary["elements"].append({
            "object_id": element_id,
            "type": element_type,
            "text": text_content,
        })

    print(f"✅ Total elements found: {len(summary['elements'])}")
    return summary

def main_inspect_only(
    presentation_id: str,
    slide_index: int,
    credentials_file: str = SERVICE_ACCOUNT_FILE,
):
    """
    Main entry point for inspection only.
    Calls exactly ONE slide-inspection function.
    """

    slides_service, _ = get_services(credentials_file)

    presentation = slides_service.presentations().get(
        presentationId=presentation_id
    ).execute()

    return inspect_slide_objects(
        presentation=presentation,
        slide_index=slide_index,
    )

def inspect_all_slides(
    presentation_id: str,
    credentials_file: str = SERVICE_ACCOUNT_FILE,
):
    """
    Inspect all slides in a presentation.
    - No recursion
    - One API fetch
    - Reuses inspect_slide_objects only
    """

    slides_service, _ = get_services(credentials_file)

    presentation = slides_service.presentations().get(
        presentationId=presentation_id
    ).execute()

    slides = presentation.get("slides", [])
    results = []

    print(f"\n📊 Inspecting {len(slides)} slides total")

    for index in range(len(slides)):
        result = inspect_slide_objects(
            presentation=presentation,
            slide_index=index,
        )
        results.append(result)

    return results


# ---------- Main execution ----------
if __name__ == "__main__":
    PRESENTATION_ID = "1mAU9N-nq3D__cc3Ioxq4jwpap5s5AYt0"
    
    all_inspections = inspect_all_slides(PRESENTATION_ID)

    # Optional: save for later analysis
    with open("slide_inspection.json", "w", encoding="utf-8") as f:
        json.dump(all_inspections, f, indent=2)

    print("\n✅ Inspection complete. Output saved to slide_inspection.json")
