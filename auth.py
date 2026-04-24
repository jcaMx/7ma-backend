import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Union

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger("slide-updater")
BASE_DIR = Path(__file__).resolve().parent

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]
SLIDES_SCOPES = ["https://www.googleapis.com/auth/presentations"]
SERVICE_ACCOUNT_FILE = str(BASE_DIR / "credentials.json")
OAUTH_CLIENT_SECRET_FILE = str(BASE_DIR / "client_secret.json")
OAUTH_TOKEN_FILE = str(BASE_DIR / "token.json")
USE_OAUTH = True


def _normalize_scopes(scopes: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(scopes or DEFAULT_SCOPES)


def _token_file_for_scopes(scopes: tuple[str, ...]) -> str:
    if scopes == tuple(DEFAULT_SCOPES):
        return OAUTH_TOKEN_FILE

    suffix = "_".join(scope.rsplit("/", 1)[-1] for scope in scopes)
    return str(BASE_DIR / f"token_{suffix}.json")


def _resolve_client_secret_file() -> str:
    if os.path.exists(OAUTH_CLIENT_SECRET_FILE):
        return OAUTH_CLIENT_SECRET_FILE

    matches = sorted(BASE_DIR.glob("client_secret*.json"))
    if matches:
        logger.warning(
            "OAuth client secret file %s was missing; using %s instead.",
            OAUTH_CLIENT_SECRET_FILE,
            matches[0],
        )
        return str(matches[0])

    raise FileNotFoundError(
        f"OAuth client secret file not found. Expected {OAUTH_CLIENT_SECRET_FILE}"
    )


def get_oauth_credentials(scopes: Iterable[str] | None = None):
    """Authorize user via OAuth 2.0 and cache token per scope set."""
    scopes = _normalize_scopes(scopes)
    token_file = _token_file_for_scopes(scopes)
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                _resolve_client_secret_file(),
                list(scopes),
            )
            creds = flow.run_local_server(port=0)

        with open(token_file, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return creds


@lru_cache(maxsize=None)
def get_services(
    credentials_file: str = SERVICE_ACCOUNT_FILE,
    scopes: Iterable[str] | None = None,
):
    """Create Slides & Drive clients using OAuth or Service Account."""
    scopes = _normalize_scopes(scopes)

    if USE_OAUTH:
        logger.info("Using OAuth 2.0 user credentials")
        credentials = get_oauth_credentials(scopes)
    else:
        logger.info("Using Service Account credentials")
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=list(scopes),
        )

    slides = build("slides", "v1", credentials=credentials)
    drive = build("drive", "v3", credentials=credentials)
    return slides, drive
