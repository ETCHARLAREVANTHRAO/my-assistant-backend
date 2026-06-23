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
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        cred = credentials.Certificate(json.loads(service_account_json))
    else:
        cred = credentials.Certificate("firebase-service-account.json")
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
