import io, os, sys, json
sys.path.insert(0, '.')
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\revanth.etcharla\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from app.core.rag import _extract_text

creds = service_account.Credentials.from_service_account_file('drive-service-account.json', scopes=['https://www.googleapis.com/auth/drive.readonly'])
service = build('drive', 'v3', credentials=creds)

resp = service.files().list(q="'1UuDF7Rx8zY6r-TQVcb2YpikjBOrJE9Jk' in parents and trashed=false and name='CS'", fields='files(id,name)').execute()
outer_cs_id = resp['files'][0]['id']
# Nested: outer "CS" folder contains a single inner "CS" folder with the actual 23 papers
resp = service.files().list(q=f"'{outer_cs_id}' in parents and trashed=false and name='CS'", fields='files(id,name)').execute()
inner_cs_id = resp['files'][0]['id']
resp = service.files().list(q=f"'{inner_cs_id}' in parents and trashed=false", fields='files(id,name,size)').execute()
files = resp['files']
print(f'Found {len(files)} CS year papers', file=sys.stderr)

os.makedirs('cs_ocr_cache', exist_ok=True)
progress = {}

for f in sorted(files, key=lambda x: int(x.get('size', 0))):
    cache_path = f"cs_ocr_cache/{f['name']}.txt"
    if os.path.exists(cache_path):
        print(f"SKIP (cached): {f['name']}", file=sys.stderr)
        progress[f['name']] = 'cached'
        continue
    try:
        request = service.files().get_media(fileId=f['id'])
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        content = buf.getvalue()
        text = _extract_text(content, f['name'])
        with open(cache_path, 'w', encoding='utf-8') as out:
            out.write(text)
        print(f"OK: {f['name']} -> {len(text)} chars", file=sys.stderr)
        progress[f['name']] = 'done'
    except Exception as e:
        print(f"FAILED: {f['name']}: {e}", file=sys.stderr)
        progress[f['name']] = f'failed: {e}'

with open('cs_ocr_progress.json', 'w') as f:
    json.dump(progress, f, indent=2)
print('ALL DONE', file=sys.stderr)
