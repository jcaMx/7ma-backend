from flask import Flask, request, jsonify
from flask_cors import CORS
import threading, uuid
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
            "error": None
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
        "slides_url": job.get("slides_url")
    })


if __name__ == "__main__":
    app.run(port=8000, debug=True)
