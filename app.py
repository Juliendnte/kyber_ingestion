"""Page d'accueil — vue d'ensemble du pipeline et statut des services."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.config import KYBERIA_API_URL, HF_DATASET_REPO
from src.storage import DatasetStore
from src.config import DATASET_DIR
from src.transform import KyberiaClient

st.set_page_config(
    page_title="KyberIA — Pipeline de Données",
    page_icon="🏐",
    layout="wide",
)

st.title("🏐 KyberIA — Pipeline de Données")
st.caption("Collecte · Transformation · Stockage · Publication HF Hub")

st.markdown("""
| Étape | Description | Page |
|-------|-------------|------|
| **1. Collecter** | Upload local (jusqu'à 20 Go) ou téléchargement YouTube | ← `Collecter` |
| **2. Analyser** | Traitement TrackNet via l'API KyberIA | ← `Analyser` |
| **3. Dataset** | Parcourir les vidéos et résultats locaux | ← `Dataset` |
| **4. Publier** | Push vers `{repo}` sur HF Hub | ← `Publier` |
""".format(repo=HF_DATASET_REPO))

st.divider()

col_api, col_ds, col_hf = st.columns(3)

with col_api:
    st.subheader("API KyberIA")
    client = KyberiaClient(KYBERIA_API_URL)
    if client.ping():
        st.success(f"Disponible\n\n`{KYBERIA_API_URL}`")
    else:
        st.warning(f"Non disponible\n\n`{KYBERIA_API_URL}`\n\nLancez `docker compose up` dans KyberIA.")

with col_ds:
    st.subheader("Dataset local")
    store = DatasetStore(DATASET_DIR)
    s = store.stats()
    st.metric("Vidéos totales", s["total"])
    st.metric("Analysées", s["analyzed"])
    st.metric("Taille", f"{s['size_go']} Go")

with col_hf:
    st.subheader("HuggingFace Hub")
    if HF_DATASET_REPO:
        st.info(f"`{HF_DATASET_REPO}`")
        st.markdown(
            f"[Voir le dépôt](https://huggingface.co/datasets/{HF_DATASET_REPO})"
        )
    else:
        st.warning("Configurez `HF_DATASET_REPO` dans `.env`")
