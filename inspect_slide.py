
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



# ---------- Main execution ----------
if __name__ == "__main__":
    PRESENTATION_ID = "your-presentation-id-here"
    SLIDE_INDEX = 4  # zero-based (slide 5 in UI)

    inspection_result = main_inspect_only(
        presentation_id=PRESENTATION_ID,
        slide_index=SLIDE_INDEX,
    )

    print("\n📦 Inspection summary:")
    print(json.dumps(inspection_result, indent=2))

    print("\n✅ Inspection completed.")