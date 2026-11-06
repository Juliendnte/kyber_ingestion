"""Étape 1 — Collecte depuis source réelle : upload local ou YouTube."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collect import download_youtube, get_video_metadata, save_uploaded_file
from src.config import DATASET_DIR, UPLOADS_DIR
from src.storage import DatasetStore

st.set_page_config(page_title="Collecter — KyberIA", page_icon="📥", layout="wide")
st.title("📥 Collecte de données")

store = DatasetStore(DATASET_DIR)

tab_up, tab_yt = st.tabs(["📁 Upload local", "▶️ YouTube"])

# ──────────────────────────────────────────────────────────────────────────────
# Onglet 1 : upload fichier local
# ──────────────────────────────────────────────────────────────────────────────
with tab_up:
    st.markdown(
        "Déposez une vidéo de match. "
        "Limite configurée : **20 Go** — couvre ~3h15 en 1080p."
    )

    source_label = st.text_input(
        "Description / source",
        placeholder="ex : Match France-Brésil, Ligue A nov. 2024",
        key="up_src",
    )
    uploaded = st.file_uploader(
        "Vidéo",
        type=["mp4", "avi", "mov", "mkv", "m4v", "ts"],
        key="up_file",
    )

    if uploaded:
        size_go = uploaded.size / (1024 ** 3)
        st.caption(f"Fichier : {uploaded.name} · {size_go:.2f} Go")

    if uploaded and st.button("💾 Ajouter au dataset", type="primary", key="up_btn"):
        bar = st.progress(0, text="Sauvegarde en cours…")
        status = st.empty()


        def on_progress(written: int, _total: int):
            go_written = written / (1024 ** 3)
            pct = min(int(go_written / size_go * 100), 99) if size_go > 0 else 0
            bar.progress(pct, text=f"{go_written:.2f} / {size_go:.2f} Go écrits")


        try:
            tmp = save_uploaded_file(uploaded, UPLOADS_DIR, uploaded.name, on_progress)
            bar.progress(100, text="Fichier reçu")

            with st.spinner("Extraction des métadonnées…"):
                meta = get_video_metadata(tmp)
                meta["source"] = source_label or "upload"
                meta["original_filename"] = uploaded.name

            entry_id = store.add_raw_video(tmp, extra=meta)
            status.success(f"✅ Ajouté au dataset : `{entry_id}`")
            st.json(meta)

        except Exception as exc:
            bar.empty()
            st.error(f"Erreur : {exc}")

# ──────────────────────────────────────────────────────────────────────────────
# Onglet 2 : téléchargement YouTube
# ──────────────────────────────────────────────────────────────────────────────
with tab_yt:
    st.markdown(
        "Télécharge une vidéo publique YouTube via **yt-dlp**. "
        "Idéal pour des extraits de matchs ou des highlights officiels."
    )

    yt_url = st.text_input(
        "URL YouTube",
        placeholder="https://www.youtube.com/watch?v=…",
        key="yt_url",
    )
    yt_quality = st.selectbox(
        "Qualité maximale",
        [
            "best[height<=1080]",
            "best[height<=720]",
            "best[height<=480]",
            "best",
        ],
        format_func=lambda x: {
            "best[height<=1080]": "1080p",
            "best[height<=720]": "720p",
            "best[height<=480]": "480p",
            "best": "Meilleure disponible",
        }.get(x, x),
        key="yt_quality",
    )
    yt_source = st.text_input(
        "Description",
        placeholder="ex : Highlights Ligue A — journée 5",
        key="yt_src",
    )

    if yt_url and st.button("Télécharger", type="primary", key="yt_btn"):
        log_area = st.empty()
        lines: list[str] = []


        def on_line(line: str):
            lines.append(line)
            log_area.code("\n".join(lines[-8:]), language="bash")


        with st.spinner("Téléchargement yt-dlp en cours…"):
            try:
                tmp = download_youtube(yt_url, UPLOADS_DIR, yt_quality, on_line)
                log_area.empty()

                with st.spinner("Extraction des métadonnées…"):
                    meta = get_video_metadata(tmp)
                    meta["source"] = yt_source or yt_url
                    meta["youtube_url"] = yt_url

                entry_id = store.add_raw_video(tmp, extra=meta)
                st.success(f"✅ Téléchargé et ajouté : `{entry_id}`")
                st.json(meta)

            except Exception as exc:
                log_area.empty()
                st.error(f"Erreur : {exc}")

