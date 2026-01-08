from flask import Flask, request, jsonify
from flask_cors import CORS
import threading, uuid
from services.jobs import jobs, jobs_lock
from services.pipeline import run_full_pipeline

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.post("/api/presentation")
def create_presentation():
    data = request.get_json(force=True, silent=True) or {}
    request_id = f"req_{uuid.uuid4().hex[:8]}"

    with jobs_lock:
        job = jobs.get(request_id) or {}
        job["status"] = "processing"
        job["slides_url"] = None
        
        job["error"] = None
        jobs[request_id] = job

    threading.Thread(
        target=run_full_pipeline,
        args=(request_id, data),
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
