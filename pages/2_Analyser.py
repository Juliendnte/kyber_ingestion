"""Étape 2 — Transformation : soumet les vidéos brutes au pipeline KyberIA."""
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DATASET_DIR, KYBERIA_API_TOKEN, KYBERIA_API_URL
from src.storage import DatasetStore
from src.transform import KyberiaClient

st.set_page_config(page_title="Analyser — KyberIA", page_icon="⚙️", layout="wide")
st.title("⚙️ Analyse via pipeline KyberIA")

store = DatasetStore(DATASET_DIR)
client = KyberiaClient(KYBERIA_API_URL, KYBERIA_API_TOKEN)

# ── Statut API ────────────────────────────────────────────────────────────────
api_ok = client.ping()
if api_ok:
    st.success(f"API KyberIA disponible — `{KYBERIA_API_URL}`")
else:
    st.error(
        f"API KyberIA non disponible (`{KYBERIA_API_URL}`). "
        "Lancez `docker compose up -d` dans le dossier KyberIA."
    )
    st.stop()

# ── Sélection de l'entrée ──────────────────────────────────────────────────────
entries = store.get_entries()
raw_entries = [e for e in entries if e.get("status") == "raw"]

if not raw_entries:
    st.info("Aucune vidéo en attente. Ajoutez-en une via la page **Collecter**.")
    st.stop()

entry_labels = {
    e["entry_id"]: f"{e['entry_id']} — {e.get('source', '?')} ({e.get('duration_human', '?')})"
    for e in raw_entries
}
selected_id = st.selectbox(
    "Vidéo à analyser",
    list(entry_labels.keys()),
    format_func=lambda x: entry_labels[x],
)
selected_entry = next(e for e in raw_entries if e["entry_id"] == selected_id)

col_info, col_action = st.columns([2, 1])
with col_info:
    st.json(
        {
            k: selected_entry[k]
            for k in ["entry_id", "source", "duration_human", "size_human", "width", "height", "fps"]
            if k in selected_entry
        }
    )

with col_action:
    st.markdown("### Lancer l'analyse")
    st.caption(
        "Le pipeline KyberIA applique TrackNet V2 (détection ballon), "
        "game_state (JEU/NON_JEU) et trajectory (lissage + contacts)."
    )
    run_btn = st.button("Analyser", type="primary", disabled=not api_ok)

if run_btn:
    video_path = store.root / "videos" / selected_id / "raw.mp4"

    st.divider()
    status_box = st.empty()
    progress_bar = st.progress(0)
    log_box = st.empty()

    try:
        # 1. Upload
        status_box.info("Upload de la vidéo vers KyberIA…")
        with st.spinner("Upload en cours (peut prendre quelques minutes pour les grands fichiers)…"):
            job_id = client.submit(video_path)
        status_box.info(f"Job créé : `{job_id}`")
        progress_bar.progress(10)

        # 2. Poll
        status_box.info("Analyse en cours…")
        tick_count = [0]
        start_t = time.time()

        def on_tick(state: str, elapsed: int):
            tick_count[0] += 1
            mins = elapsed // 60
            secs = elapsed % 60
            pct = min(10 + tick_count[0] * 2, 90)
            progress_bar.progress(pct)
            log_box.markdown(
                f"**État** : `{state}` · **Écoulé** : {mins}m{secs:02d}s"
            )

        result = client.wait(job_id, poll=10, on_tick=on_tick)
        progress_bar.progress(90)
        status_box.info("Récupération des résultats…")

        # 3. Télécharger CSV + vidéo annotée
        tmp_csv = DATASET_DIR / f"{job_id}_analysis.csv"
        tmp_video = DATASET_DIR / f"{job_id}_analyzed.mp4"

        client.fetch_csv(job_id, tmp_csv)
        client.fetch_video(job_id, tmp_video)

        # 4. Attacher au dataset
        store.add_results(selected_id, csv_path=tmp_csv, video_path=tmp_video)
        tmp_csv.unlink(missing_ok=True)
        tmp_video.unlink(missing_ok=True)

        progress_bar.progress(100)
        elapsed_total = int(time.time() - start_t)
        status_box.success(
            f"Analyse terminée en {elapsed_total // 60}m{elapsed_total % 60:02d}s — "
            f"résultats attachés à `{selected_id}`."
        )
        log_box.empty()

    except Exception as exc:
        status_box.error(f"Erreur : {exc}")
