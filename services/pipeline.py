import time
import traceback
from services.jobs import jobs, jobs_lock
from content_generator import run_pipeline, sanitize_filename
from audio_generator import generate_tts_audio_from_file
from slide_updater import update_slides, slide_map  # if needed
import os
from services.email_utils import send_email_api
import logging
from config import RESULT_DELIVERY_MODE

logger = logging.getLogger(__name__)

print("🔥 PIPELINE MODULE LOADED")


def run_full_pipeline(request_id: str, payload: dict):
    """
    Full 7MA pipeline for a given request ID.
    Updates jobs[request_id] with status, slides URL, or error.
    """
    print("🚀 PIPELINE STARTED", request_id)
    try:
        # Step 1: Generate structured content
        try:
            print("🚀 Pipeline started", request_id)
            print("📦 Input data:", payload)
        except Exception as e:
            print(f"[pipeline] Error starting pipeline: {e}")
            traceback.print_exc()
            return

        result = run_pipeline(payload)
        print("🔍 Pipeline result:", result)


        print("🔑 result keys:", result.keys())

        

        # Optional: Construct output dir using sanitized name
        user_name = payload.get("name", "anonymous")
        safe_name = sanitize_filename(user_name)
        output_dir = os.path.join("output", safe_name)
        os.makedirs(output_dir, exist_ok=True)

        #Prepare path BEFORE TTS
        capability_json_path = os.path.join(output_dir, "capability_scripts.json")

        

        # Step 2: Generate audio files if capability_scripts exist
        # if result.get("capability_scripts"):
        #     try:
        #         import json

        #         # Save capability scripts
        #         with open(capability_json_path, "w", encoding="utf-8") as f:
        #             json.dump(result["capability_scripts"], f, indent=2, ensure_ascii=False)

        #         print("✅ Capability scripts saved to:", capability_json_path)

        #         # 🔊 Generate TTS audio
        #         generate_tts_audio_from_file(capability_json_path)
        #         print("🔊 Audio generation completed")

        #     except Exception as audio_err:
        #         print(f"[pipeline] Audio generation failed: {audio_err}")
        #         traceback.print_exc()

        presentation_id = payload.get("presentation_id") or os.getenv("PRESENTATION_ID")
        if not presentation_id:
            raise ValueError(
                "presentation_id is required. Provide it in the request payload or set PRESENTATION_ID environment variable."
            )

        print("📦 capability_use_cases:", result.get("capability_use_cases"))
        print("🧪 result type:", type(result))
        print("🧪 result keys:", result.keys() if isinstance(result, dict) else "NOT A DICT")


        # Step 3: Update Google Slides
        slides_url = update_slides(
            presentation_id,
            slide_map,
            result,
            audio_dir=output_dir + "/audio_files",
            create_new_presentation=False
        )
        print("✅ Slides updated to:", slides_url)

        # Step 4: Update job status
        with jobs_lock:
            jobs[request_id]["status"] = "completed"
            jobs[request_id]["slides_url"] = slides_url
            jobs[request_id]["email"] = payload.get("email")

        print("✅ Job status updated to:", jobs[request_id]["status"])

        # Step 5: Deliver result (email / app / both)
        email = jobs[request_id].get("email")
        print(f"📧 Email delivery check - RESULT_DELIVERY_MODE: {RESULT_DELIVERY_MODE}, email: {email}")
        
        if RESULT_DELIVERY_MODE in ("email", "both") and email:
            print(f"📧 Attempting to send email to {email}")
            try:
                send_email_api(
                    to_email=email,
                    body=slides_url,
                )
                logger.info(f"📧 Slides emailed to {email}")
                print(f"✅ Email sent successfully to {email}")
            except Exception as email_err:
                # Email failure should NOT fail the job
                error_msg = f"❌ Failed to send email: {email_err}"
                logger.exception(error_msg)
                print(error_msg)
        else:
            if not email:
                print("⚠️ Email not sent: no email address provided")
            elif RESULT_DELIVERY_MODE not in ("email", "both"):
                print(f"⚠️ Email not sent: RESULT_DELIVERY_MODE is '{RESULT_DELIVERY_MODE}' (not 'email' or 'both')")



        
        
    except Exception as e:
        with jobs_lock:
            jobs[request_id]["status"] = "error"
            jobs[request_id]["error"] = str(e)
        print(f"[pipeline] Error processing request {request_id}: {e}")
        traceback.print_exc()

