import os, ssl

# Disable SSL verification before anything else
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["HF_HUB_DISABLE_SSL_VERIFICATION"] = "1"
os.environ["HF_HUB_DISABLE_XET"] = "1"        # force legacy download (no XET CDN)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

ssl._create_default_https_context = ssl._create_unverified_context

# Patch requests to never verify SSL
import urllib3
urllib3.disable_warnings()
import requests
_orig = requests.Session.send
def _no_verify(self, r, **kw):
    kw["verify"] = False
    return _orig(self, r, **kw)
requests.Session.send = _no_verify

print("Downloading all-MiniLM-L6-v2 ...")
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Done! Model cached — server will work offline from now on.")
