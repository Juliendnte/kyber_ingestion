import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DATASET_DIR = DATA_DIR / "dataset"

for _d in [UPLOADS_DIR, DATASET_DIR / "videos"]:
    _d.mkdir(parents=True, exist_ok=True)

KYBERIA_API_URL = os.getenv("KYBERIA_API_URL", "http://localhost:8000")
KYBERIA_API_TOKEN = os.getenv("KYBERIA_API_TOKEN", "")

HF_TOKEN_WRITE = os.getenv("HF_TOKEN_WRITE", "")
HF_TOKEN = os.getenv("HF_TOKEN", HF_TOKEN_WRITE)
HF_ORG = os.getenv("HF_ORG", "ynov")
HF_DATASET_REPO = os.getenv("HF_DATASET_REPO", "ynov/kyberia-data")

# 8 Mo par chunk — équilibre mémoire/vitesse pour les grandes vidéos
CHUNK_SIZE = 8 * 1024 * 1024
