import io
import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from . import firestore_service
from .rag import _log, ingest_document

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Reserved pseudo-user for the shared admin-curated knowledge base ingested
# from Drive. Never a real Firebase UID, so it can't collide with a real user
# and is invisible in any per-user Documents listing (which is keyed by the
# caller's own UID) — it only surfaces as retrieved context during chat.
GLOBAL_KNOWLEDGE_USER_ID = "__global__"

# Native Google Docs types have no raw bytes — they must be exported to a real format.
GOOGLE_DOC_EXPORTS = {
    "application/vnd.google-apps.document": ("text/plain", "txt"),
}

SUPPORTED_EXTENSIONS = {"md", "txt", "pdf", "docx", "jpg", "jpeg", "png", "bmp", "tiff", "webp"}

_drive_service = None


def _get_drive_service():
    global _drive_service
    if _drive_service is not None:
        return _drive_service

    service_account_json = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    if service_account_json:
        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    elif os.path.exists("drive-service-account.json"):
        creds = service_account.Credentials.from_service_account_file(
            "drive-service-account.json", scopes=SCOPES
        )
    else:
        raise RuntimeError(
            "Google Drive credentials not found. Set GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON env var "
            "or place drive-service-account.json in the backend/ directory."
        )

    _drive_service = build("drive", "v3", credentials=creds)
    return _drive_service


def list_folder_files(folder_id: str) -> list[dict]:
    """List all non-trashed, non-folder files directly inside a Drive folder."""
    service = _get_drive_service()
    files: list[dict] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
            pageToken=page_token,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return [f for f in files if f["mimeType"] != "application/vnd.google-apps.folder"]


def _download_file(file: dict) -> tuple[bytes, str]:
    """Download (or export) a Drive file's bytes. Returns (content_bytes, filename)."""
    service = _get_drive_service()
    mime_type = file["mimeType"]
    name = file["name"]

    if mime_type in GOOGLE_DOC_EXPORTS:
        export_mime, ext = GOOGLE_DOC_EXPORTS[mime_type]
        request = service.files().export_media(fileId=file["id"], mimeType=export_mime)
        if not name.lower().endswith(f".{ext}"):
            name = f"{name}.{ext}"
    else:
        request = service.files().get_media(fileId=file["id"])

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue(), name


def sync_folder(folder_id: str) -> dict:
    """
    List files in the given Drive folder and ingest any new/changed ones into
    the shared global knowledge base (GLOBAL_KNOWLEDGE_USER_ID) — never a
    per-user bucket. Every user's chat queries draw on this automatically,
    alongside whatever they've personally uploaded, but it never appears in
    anyone's Documents list or storage quota. Unsupported file types are skipped.
    Returns {"ingested": [...], "skipped": [...], "failed": [...]}.
    """
    files = list_folder_files(folder_id)
    already_synced = firestore_service.get_drive_sync_state(GLOBAL_KNOWLEDGE_USER_ID)

    ingested, skipped, failed = [], [], []

    for f in files:
        is_google_doc = f["mimeType"] in GOOGLE_DOC_EXPORTS
        ext = f["name"].rsplit(".", 1)[-1].lower() if "." in f["name"] else ""
        if not is_google_doc and ext not in SUPPORTED_EXTENSIONS:
            skipped.append(f["name"])
            continue

        if already_synced.get(f["id"]) == f["modifiedTime"]:
            continue  # unchanged since last sync

        try:
            content_bytes, filename = _download_file(f)
            chunks, text = ingest_document(content_bytes, filename, GLOBAL_KNOWLEDGE_USER_ID)
            firestore_service.add_document(
                GLOBAL_KNOWLEDGE_USER_ID, filename, len(content_bytes), chunks, text
            )
            firestore_service.set_drive_sync_state(
                GLOBAL_KNOWLEDGE_USER_ID, f["id"], f["modifiedTime"], filename
            )
            ingested.append(filename)
        except Exception as e:
            _log(f"DRIVE SYNC ERROR [{f['name']}]: {e}")
            failed.append(f["name"])

    return {"ingested": ingested, "skipped": skipped, "failed": failed}
