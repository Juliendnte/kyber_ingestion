"""
CLI pour ajouter une vidéo déjà présente sur disque sans passer par l'interface.
Utile pour les vidéos très volumineuses ou les ajouts en lot.

Usage :
    uv run scripts/add_local_video.py /chemin/vers/match.mp4 --source "Ligue A J5"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collect import get_video_metadata
from src.config import DATASET_DIR
from src.storage import DatasetStore


def main():
    parser = argparse.ArgumentParser(description="Ajoute une vidéo locale au dataset KyberIA")
    parser.add_argument("video", type=Path, help="Chemin vers la vidéo")
    parser.add_argument("--source", default="", help="Description / source")
    parser.add_argument("--entry-id", default=None, help="ID manuel (généré auto si absent)")
    parser.add_argument("--move", action="store_true", help="Déplacer au lieu de copier")
    args = parser.parse_args()

    if not args.video.exists():
        print(f"Erreur : fichier introuvable — {args.video}", file=sys.stderr)
        sys.exit(1)

    store = DatasetStore(DATASET_DIR)

    print(f"Lecture des métadonnées : {args.video.name}…")
    meta = get_video_metadata(args.video)
    meta["source"] = args.source or str(args.video)

    # Copie ou déplacement
    import shutil
    from datetime import datetime

    entry_id = args.entry_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    entry_dir = DATASET_DIR / "videos" / entry_id
    entry_dir.mkdir(parents=True, exist_ok=True)

    dest = entry_dir / "raw.mp4"
    if args.move:
        shutil.move(str(args.video), dest)
        print(f"Déplacé → {dest}")
    else:
        print(f"Copie ({meta.get('size_human', '?')})…")
        shutil.copy2(args.video, dest)
        print(f"Copié → {dest}")

    # Enregistrer dans l'index (on passe dest directement, add_raw_video attend un path à déplacer)
    # Ici le fichier est déjà à sa place, on reconstruit l'entrée manuellement
    import json
    from datetime import datetime as dt

    m = {"entry_id": entry_id, "added_at": dt.now().isoformat(), "status": "raw", **meta}
    (entry_dir / "meta.json").write_text(
        json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    store._meta["entries"][entry_id] = {
        "status": "raw",
        "added_at": m["added_at"],
        "source": m.get("source", ""),
    }
    store._flush()

    print(f"\nEntrée créée : {entry_id}")
    print(f"   Durée   : {meta.get('duration_human', '?')}")
    print(f"   Taille  : {meta.get('size_human', '?')}")
    print(f"   Source  : {meta.get('source')}")


if __name__ == "__main__":
    main()
