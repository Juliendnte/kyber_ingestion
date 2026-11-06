"""
Stockage — étape 3 du pipeline.
Gère le dataset local : ajout de vidéos, résultats d'analyse, index, stats.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

SCHEMA_VERSION = "1.0"


class DatasetStore:
    """
    Dataset local structuré prêt pour l'upload HF Hub.

    data/dataset/
        metadata.json
        videos/
            {entry_id}/
                raw.mp4
                analyzed.mp4   (optionnel)
                analysis.csv   (optionnel)
                meta.json
    """

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._meta_path = self.root / "metadata.json"
        self._load_or_init()

    def _load_or_init(self):
        if self._meta_path.exists():
            with open(self._meta_path, encoding="utf-8") as f:
                self._meta = json.load(f)
        else:
            self._meta = {
                "schema_version": SCHEMA_VERSION,
                "created_at": datetime.now().isoformat(),
                "entries": {},
            }
            self._flush()

    def _flush(self):
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump(self._meta, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def add_raw_video(
            self,
            video_path: Path,
            entry_id: Optional[str] = None,
            extra: Optional[dict] = None,
    ) -> str:
        """
        Déplace la vidéo dans le dataset et crée l'entrée.
        Retourne l'entry_id généré.
        """
        if entry_id is None:
            entry_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        entry_dir = self.root / "videos" / entry_id
        entry_dir.mkdir(parents=True, exist_ok=True)

        shutil.move(str(video_path), entry_dir / "raw.mp4")

        meta = {
            "entry_id": entry_id,
            "added_at": datetime.now().isoformat(),
            "status": "raw",
            **(extra or {}),
        }
        (entry_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        self._meta["entries"][entry_id] = {
            "status": "raw",
            "added_at": meta["added_at"],
            "source": meta.get("source", "upload"),
        }
        self._flush()
        return entry_id

    def add_results(
            self,
            entry_id: str,
            csv_path: Optional[Path] = None,
            video_path: Optional[Path] = None,
    ):
        """Attache les sorties KyberIA à une entrée existante."""
        entry_dir = self.root / "videos" / entry_id
        if not entry_dir.exists():
            raise ValueError(f"Entrée inconnue : {entry_id}")

        if csv_path and csv_path.exists():
            shutil.copy2(csv_path, entry_dir / "analysis.csv")
        if video_path and video_path.exists():
            shutil.copy2(video_path, entry_dir / "analyzed.mp4")

        meta_path = entry_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["status"] = "analyzed"
        meta["analyzed_at"] = datetime.now().isoformat()
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        self._meta["entries"][entry_id]["status"] = "analyzed"
        self._flush()

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def get_entries(self) -> list[dict]:
        entries = []
        for entry_id in self._meta["entries"]:
            meta_path = self.root / "videos" / entry_id / "meta.json"
            if meta_path.exists():
                m = json.loads(meta_path.read_text(encoding="utf-8"))
                m["files"] = [f.name for f in (self.root / "videos" / entry_id).iterdir()]
                entries.append(m)
        return sorted(entries, key=lambda x: x.get("added_at", ""), reverse=True)

    def get_csv(self, entry_id: str) -> Optional[pd.DataFrame]:
        csv_path = self.root / "videos" / entry_id / "analysis.csv"
        if csv_path.exists():
            return pd.read_csv(csv_path)
        return None

    def stats(self) -> dict:
        entries = self.get_entries()
        analyzed = [e for e in entries if e.get("status") == "analyzed"]

        total_bytes = sum(
            f.stat().st_size
            for e in entries
            for f in (self.root / "videos" / e["entry_id"]).iterdir()
            if f.is_file()
        )
        return {
            "total": len(entries),
            "analyzed": len(analyzed),
            "pending": len(entries) - len(analyzed),
            "size_go": round(total_bytes / (1024 ** 3), 2),
        }

    # ------------------------------------------------------------------
    # Dataset card
    # ------------------------------------------------------------------

    def dataset_card(self) -> str:
        s = self.stats()
        return f"""\
---
license: cc-by-4.0
task_categories:
- object-detection
- video-classification
language:
- fr
tags:
- volleyball
- ball-tracking
- sports-analytics
- tracknet
---

# KyberIA — Analyse de Matchs de Volleyball

Dataset produit par le pipeline **KyberIA** (Aix Ynov Campus × FFVB).
Chaque entrée contient la vidéo d'origine + l'analyse TrackNet V2 du ballon.

## Structure

```
videos/{{id}}/
    raw.mp4          # Vidéo originale
    analyzed.mp4     # Vidéo avec overlay trajectoire (si disponible)
    analysis.csv     # Résultats frame par frame
    meta.json        # Métadonnées (source, durée, résolution…)
```

## Colonnes CSV

| Colonne | Description |
|---------|-------------|
| `frame` | Numéro de frame |
| `time_sec` | Temps en secondes |
| `ball_present` | Ballon détecté (0/1) |
| `x`, `y` | Position brute |
| `confidence` | Score TrackNet |
| `game_state` | `JEU` / `NON_JEU` |
| `smooth_x`, `smooth_y` | Position lissée Savitzky-Golay |
| `angle` | Angle de trajectoire |
| `traj_change` | Changement de direction — proxy contact joueur |
| `direction` | Direction principale |

## Statistiques

| | |
|--|--|
| Vidéos totales | {s['total']} |
| Analysées | {s['analyzed']} |
| Taille totale | {s['size_go']} Go |
"""

