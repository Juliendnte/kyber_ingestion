"""Étape 4 — Publication vers HuggingFace Hub (ynov/kyberia-data)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DATASET_DIR, HF_DATASET_REPO, HF_TOKEN_WRITE
from src.publish import HFPublisher
from src.storage import DatasetStore

st.set_page_config(page_title="Publier — KyberIA", page_icon="🚀", layout="wide")
st.title("Publication HuggingFace Hub")

store = DatasetStore(DATASET_DIR)
stats = store.stats()
entries = store.get_entries()

# ── Configuration ─────────────────────────────────────────────────────────────
st.subheader("Configuration")
col_tok, col_repo = st.columns(2)

with col_tok:
    token = st.text_input(
        "Token HF (write)",
        value=HF_TOKEN_WRITE,
        type="password",
        help="HF_TOKEN_WRITE dans votre .env",
    )
with col_repo:
    repo_id = st.text_input(
        "Dépôt dataset",
        value=HF_DATASET_REPO,
        help="Format : org/nom-du-repo",
    )

if not token:
    st.warning("Renseignez votre token HuggingFace pour publier.")
    st.stop()

publisher = HFPublisher(token=token, repo_id=repo_id)

# ── Aperçu du dataset card ────────────────────────────────────────────────────
with st.expander("Aperçu du dataset card (README.md)"):
    st.markdown(store.dataset_card())

st.divider()

# ── Sélection des entrées à publier ──────────────────────────────────────────
st.subheader("Sélectionner les entrées à publier")

analyzed = [e for e in entries if e.get("status") == "analyzed"]
if not analyzed:
    st.info("Aucune entrée analysée. Passez par **Analyser** d'abord.")
    st.stop()

entry_options = {
    e["entry_id"]: f"{e['entry_id']} — {e.get('source', '?')} ({e.get('duration_human', '?')})"
    for e in analyzed
}
selected_ids = st.multiselect(
    "Entrées",
    list(entry_options.keys()),
    default=list(entry_options.keys()),
    format_func=lambda x: entry_options[x],
)

st.caption(f"{len(selected_ids)} entrée(s) sélectionnée(s)")

col_pub, col_card = st.columns(2)

# ── Publier tout ──────────────────────────────────────────────────────────────
with col_pub:
    if st.button("Publier la sélection", type="primary", disabled=not selected_ids):
        try:
            with st.spinner("Création / vérification du dépôt HF…"):
                publisher.ensure_repo()

            overall = st.progress(0, text="Démarrage…")
            entry_status = st.empty()

            def on_entry(eid: str, i: int, total: int):
                overall.progress(
                    int(i / total * 95),
                    text=f"Entrée {i}/{total} : {eid}",
                )
                entry_status.info(f"⬆️ Upload `{eid}`…")

            publisher.upload_all(store, entry_ids=selected_ids, on_entry=on_entry)

            overall.progress(100, text="Terminé")
            entry_status.empty()
            st.success(
                f"{len(selected_ids)} entrée(s) publiée(s) sur "
                f"[{repo_id}](https://huggingface.co/datasets/{repo_id})"
            )

        except Exception as exc:
            st.error(f"Erreur lors de la publication : {exc}")

# ── Mettre à jour le dataset card uniquement ─────────────────────────────────
with col_card:
    if st.button("Mettre à jour uniquement le README"):
        try:
            with st.spinner("Envoi du README…"):
                publisher.ensure_repo()
                publisher.api.upload_file(
                    path_or_fileobj=store.dataset_card().encode("utf-8"),
                    path_in_repo="README.md",
                    repo_id=repo_id,
                    repo_type="dataset",
                    token=token,
                    commit_message="Update dataset card",
                )
            st.success("README mis à jour")
        except Exception as exc:
            st.error(f"Erreur : {exc}")

# ── Lien direct ──────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    f"Dépôt HF : [huggingface.co/datasets/{repo_id}](https://huggingface.co/datasets/{repo_id})"
)
