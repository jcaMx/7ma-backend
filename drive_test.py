from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

# =========================
# CONFIG
# =========================
SERVICE_ACCOUNT_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]
TEST_FILENAME = "upload_test.txt"

# =========================
# AUTH
# =========================
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

drive = build("drive", "v3", credentials=creds)

# =========================
# CREATE FILE CONTENT
# =========================
content = b"Hello! This is a Drive upload test from a service account."

media = MediaInMemoryUpload(
    content,
    mimetype="text/plain",
    resumable=False
)

# =========================
# UPLOAD
# =========================
file_metadata = {
    "name": TEST_FILENAME
}

file = drive.files().create(
    body=file_metadata,
    media_body=media,
    fields="id,name,parents"
).execute()

print("✅ Upload successful")
print(f"   ID: {file['id']}")
print(f"   Name: {file['name']}")
print(f"   Parents: {file.get('parents')}")
