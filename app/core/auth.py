import os
import json
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_initialized = False

def _init_firebase():
    global _initialized
    if _initialized:
        return
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if service_account_json:
        cred = credentials.Certificate(json.loads(service_account_json))
    elif os.path.exists("firebase-service-account.json"):
        cred = credentials.Certificate("firebase-service-account.json")
    else:
        raise RuntimeError("Firebase credentials not found. Set FIREBASE_SERVICE_ACCOUNT_JSON env var.")
    firebase_admin.initialize_app(cred)
    _initialized = True

_init_firebase()

_bearer = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> str:
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def verify_admin_token(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> str:
    """Like verify_token, but only accepts the configured admin account."""
    try:
        decoded = auth.verify_id_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    if not admin_email or decoded.get("email", "").lower() != admin_email:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return decoded["uid"]
