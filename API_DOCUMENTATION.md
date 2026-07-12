# 7ma-backend API Documentation

This document describes the Flask API provided by `app.py` in the `7ma-backend` service.

## Base URL

Default server base URL:

- `http://localhost:8000`

All API routes are prefixed with `/api`.

---

## Endpoints

### 1. Create a presentation request

- Method: `POST`
- URL: `/api/presentation`

#### Description

Starts the presentation pipeline for a user request. The request is processed asynchronously in a background thread.

#### Request Body

JSON object containing at least:

- `email` (string, required): user email address.

Example:

```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "company": "Acme Co",
  "title": "Product Launch",
  "other_input": "..."
}
```

#### Response

- `200 OK` on success

```json
{
  "request_id": "req_12345678"
}
```

#### Error Responses

- `400 Bad Request` when `email` is missing:

```json
{
  "error": "Email is required"
}
```

- `409 Conflict` when there is already an active pipeline running for the same email:

```json
{
  "error": "Presentation already generating"
}
```

#### Notes

- The endpoint generates a `request_id` for tracking.
- Duplicate requests for the same email are blocked while a pipeline is already running.

---

### 2. Get presentation status

- Method: `GET`
- URL: `/api/presentation/<request_id>`

#### Description

Returns the current status of a presentation job.

#### Response

- `200 OK` when job exists

```json
{
  "status": "processing",
  "slides_url": null,
  "audio_download_url": null,
  "error": null
}
```

- `404 Not Found` when the job cannot be found:

```json
{
  "status": "not_found"
}
```

#### Fields

- `status` (string): current job state such as `processing`, `completed`, or `failed`.
- `slides_url` (string|null): optional URL to the generated slides resource if available.
- `audio_download_url` (string|null): URL for downloading a ZIP of audio files when available.
- `error` (string|null): error message when the pipeline failed.

---

### 3. List existing presentations

- Method: `GET`
- URL: `/api/presentations`

#### Description

Returns a list of saved presentation directories under the backend `output/` folder.

#### Response

- `200 OK`

```json
{
  "presentations": [
    {
      "folder": "barry",
      "name": "Barry Example",
      "company": "Barry Co",
      "title": "Capability Brief"
    }
  ]
}
```

#### Notes

- This endpoint scans `output/` for subfolders containing `user_input.json`.
- It ignores folders with missing or invalid `user_input.json` files.

---

### 4. Get generated deck data

- Method: `GET`
- URL: `/api/presentation/<request_id>/deck`

#### Description

Returns the generated presentation deck JSON for a given job.

#### Response

- `200 OK` with the contents of `combined_output.json`
- `404 Not Found` when the deck is not yet available or the request ID/folder does not exist:

```json
{
  "error": "Deck not available yet or not found"
}
```

#### Notes

- The endpoint first looks for a live job with `output_dir`.
- If not found, it falls back to `output/<request_id>` as a folder name.

---

### 5. Download a single audio file

- Method: `GET`
- URL: `/api/presentation/<request_id>/audio/<filename>`

#### Description

Serves a single audio file generated for the presentation.

#### Response

- `200 OK` with the audio file content
- `404 Not Found` if the job does not exist or audio files are unavailable:

```json
{
  "error": "Presentation not found"
}
```

or

```json
{
  "error": "Audio files not available"
}
```

---

### 6. Download all audio files as ZIP

- Method: `GET`
- URL: `/api/presentation/<request_id>/audio.zip`

#### Description

Packages all audio files for the presentation into a ZIP archive and returns it.

#### Response

- `200 OK` with `Content-Type: application/zip`
- `Content-Disposition: attachment; filename="<request_id>_audio_files.zip"`

#### Error Responses

- `404 Not Found` if the presentation or audio content is missing:

```json
{
  "error": "Presentation not found"
}
```

or

```json
{
  "error": "Audio files not available"
}
```

---

## Application startup

To run the backend server directly:

```bash
python app.py
```

- Default port: `8000`
- Debug mode is enabled in `app.py` when run as the main module.

---

## Internal behavior

- `pipeline_locks` prevents duplicate presentation generation for the same email address.
- `jobs` tracks the lifecycle of each request by `request_id`.
- Presentation output artifacts are stored under the `output/` directory.
- Audio downloads are served from the job's `audio_dir` path.
