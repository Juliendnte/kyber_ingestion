"""Étape 3 — Vue du dataset local : liste, stats, aperçu CSV."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DATASET_DIR
from src.storage import DatasetStore

st.set_page_config(page_title="Dataset — KyberIA", page_icon="🗂️", layout="wide")
st.title("🗂️ Dataset local")

store = DatasetStore(DATASET_DIR)
stats = store.stats()

# ── Métriques globales ──────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Vidéos totales", stats["total"])
col2.metric("Analysées", stats["analyzed"])
col3.metric("En attente", stats["pending"])
col4.metric("Taille totale", f"{stats['size_go']} Go")

st.divider()

# ── Table des entrées ────────────────────────────────────────────────────────
entries = store.get_entries()
if not entries:
    st.info("Le dataset est vide. Ajoutez des vidéos via **Collecter**.")
    st.stop()

rows = []
for e in entries:
    rows.append(
        {
            "ID": e["entry_id"],
            "Source": e.get("source", "—"),
            "Durée": e.get("duration_human", "—"),
            "Résolution": (
                f"{e.get('width')}×{e.get('height')}"
                if e.get("width") and e.get("height")
                else "—"
            ),
            "Taille": e.get("size_human", "—"),
            "Statut": e.get("status", "—"),
            "Ajouté le": e.get("added_at", "")[:19].replace("T", " "),
            "Fichiers": ", ".join(e.get("files", [])),
        }
    )

df = pd.DataFrame(rows)
status_colors = {"raw": "🟡", "analyzed": "🟢"}
df["Statut"] = df["Statut"].map(lambda s: f"{status_colors.get(s, '⚪')} {s}")

st.dataframe(df, use_container_width=True, hide_index=True)

# ── Aperçu d'une entrée ──────────────────────────────────────────────────────
st.divider()
st.subheader("Aperçu")

entry_ids = [e["entry_id"] for e in entries]
selected = st.selectbox("Sélectionner une entrée", entry_ids)

if selected:
    entry_dir = DATASET_DIR / "videos" / selected
    csv_df = store.get_csv(selected)

    if csv_df is not None:
        st.markdown(f"**{len(csv_df)} frames** · {csv_df.columns.tolist()}")

        tab_table, tab_charts = st.tabs(["Tableau", "Graphiques"])

        with tab_table:
            st.dataframe(csv_df.head(200), use_container_width=True, hide_index=True)

        with tab_charts:
            col_l, col_r = st.columns(2)

            with col_l:
                if "x" in csv_df.columns and "y" in csv_df.columns:
                    st.markdown("**Trajectoire brute (x, y)**")
                    detected = csv_df[csv_df.get("ball_present", pd.Series(1)) == 1]
                    st.line_chart(
                        detected[["x", "y"]].rename(columns={"x": "X", "y": "Y"}),
                        use_container_width=True,
                    )

            with col_r:
                if "game_state" in csv_df.columns:
                    st.markdown("**Répartition game_state**")
                    st.bar_chart(
                        csv_df["game_state"].value_counts(),
                        use_container_width=True,
                    )

            if "traj_change" in csv_df.columns:
                contacts = csv_df["traj_change"].sum()
                st.metric("Contacts détectés (traj_change = 1)", int(contacts))
    else:
        st.info("Aucun CSV disponible — analysez d'abord cette entrée.")

    # Fichiers disponibles
    st.markdown("**Fichiers présents :**")
    for f in sorted(entry_dir.iterdir()):
        size_mo = f.stat().st_size / (1024 ** 2)
        st.text(f"  {f.name}  ({size_mo:.1f} Mo)")
