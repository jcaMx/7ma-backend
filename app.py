import io
import os
import threading, uuid
import zipfile

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from services.jobs import jobs, jobs_lock
from services.pipeline import run_full_pipeline

pipeline_locks = {}
pipeline_lock = threading.Lock()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.post("/api/presentation")
def create_presentation():
    data = request.get_json(force=True, silent=True) or {}
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    request_id = f"req_{uuid.uuid4().hex[:8]}"

     # ---- DUPLICATE REQUEST GUARD ----
    with pipeline_lock:
        if pipeline_locks.get(email):
            return jsonify({
                "error": "Presentation already generating"
            }), 409
        pipeline_locks[email] = True
    # --------------------------------
    
    with jobs_lock:
        jobs[request_id] = {
            "status": "processing",
            "slides_url": None,
            "error": None,
            "audio_dir": None,
        }

    def run():
        try:
            run_full_pipeline(request_id, data)
        finally:
            # ✅ RELEASE LOCK NO MATTER WHAT
            with pipeline_lock:
                pipeline_locks.pop(email, None)

    threading.Thread(
        target=run,   
        daemon=True
    ).start()

    return jsonify({"request_id": request_id})


@app.get("/api/presentation/<request_id>")
def get_status(request_id):
    job = jobs.get(request_id)
    if not job:
        return jsonify({"status": "not_found"}), 404

    return jsonify({
        "status": job["status"],
        "slides_url": job.get("slides_url"),
        "audio_download_url": f"/api/presentation/{request_id}/audio.zip" if job.get("audio_dir") else None,
        "error": job.get("error"),
    })


@app.get("/api/presentation/<request_id>/audio.zip")
def download_audio_zip(request_id):
    job = jobs.get(request_id)
    if not job:
        return jsonify({"error": "Presentation not found"}), 404

    audio_dir = job.get("audio_dir")
    if not audio_dir or not os.path.isdir(audio_dir):
        return jsonify({"error": "Audio files not available"}), 404

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in os.listdir(audio_dir):
            filepath = os.path.join(audio_dir, filename)
            if os.path.isfile(filepath):
                archive.write(filepath, arcname=filename)

    if buffer.tell() == 0:
        return jsonify({"error": "Audio files not available"}), 404

    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        mimetype="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename=\"{request_id}_audio_files.zip\"'
        },
    )


if __name__ == "__main__":
    app.run(port=8000, debug=True)
