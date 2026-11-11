# kyber_ingestion

Pipeline de données de [KyberIA](https://github.com/Juliendnte/KYBERIA), le
projet d'analyse vidéo automatique de matchs de volleyball (YDAYS, Aix Ynov
Campus).

Cette application Streamlit sert à constituer le dataset vidéo du projet. Elle
permet de :

1. **Collecter** des vidéos de match, par upload local ou depuis YouTube ;
2. **Analyser** ces vidéos avec l'API KyberIA (TrackNet V2, détection du
   ballon) ;
3. **Stocker** vidéos, résultats et métadonnées dans un dataset local
   structuré ;
4. **Publier** ce dataset sur le Hugging Face Hub.

```
Collecter ──► data/dataset/videos/{id}/raw.mp4 + meta.json
    │
Analyser  ──► API KyberIA (:8000) ──► analysis.csv + analyzed.mp4
    │
Dataset   ──► consultation locale (stats, aperçu CSV, graphiques)
    │
Publier   ──► huggingface.co/datasets/<HF_DATASET_REPO>
```

> ⚠️ L'étape **Analyser** ne fonctionne pas encore avec l'API KyberIA
> actuelle. Voir [Limites connues](#limites-connues).

## Prérequis

- [uv](https://docs.astral.sh/uv/) : gère Python et les dépendances. La version
  de Python est fixée dans `.python-version`.
- **ffmpeg** (pour `ffprobe`), qui sert à extraire durée, résolution, fps et
  codec. Sans lui, la collecte fonctionne quand même, mais les métadonnées se
  réduisent à la taille du fichier.
  ```bash
  sudo apt install ffmpeg   # Debian / Ubuntu / WSL
  ```
- `yt-dlp` est installé avec les dépendances Python, rien à faire de plus.
- Pour l'étape Analyser : l'API KyberIA doit tourner
  (`docker compose up -d` dans le dépôt KYBERIA).
- Pour l'étape Publier : un token Hugging Face avec droit d'écriture sur le
  dépôt cible.

## Installation

```bash
git clone https://github.com/Juliendnte/kyber_ingestion.git
cd kyber_ingestion
uv sync
cp .env.example .env    # puis remplir les valeurs
```

## Configuration (`.env`)

| Variable | Défaut | Rôle |
|---|---|---|
| `KYBERIA_API_URL` | `http://localhost:8000` | URL de l'API KyberIA |
| `KYBERIA_API_TOKEN` | vide | Bearer token de l'API. Inutile si l'API tourne en `ENVIRONMENT=development` |
| `HF_TOKEN_WRITE` | vide | Token HF avec droit d'écriture, pour la publication |
| `HF_TOKEN` | `HF_TOKEN_WRITE` | Token HF en lecture seule (optionnel) |
| `HF_ORG` | `ynov` | Organisation HF |
| `HF_DATASET_REPO` | `ynov/kyberia-data` | Dépôt dataset cible, au format `org/nom` |

Le `.env` est ignoré par git. Ne jamais commiter de token.

> Un token HF « fine-grained » doit avoir la permission d'écriture **sur le
> namespace du dépôt cible**. Un token limité à l'org `ynov` ne peut pas
> écrire sur un dépôt personnel, et inversement : l'erreur est alors un
> `403 Forbidden`.

## Lancement

```bash
uv run streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501. La page d'accueil indique si
l'API KyberIA répond, ce que contient le dataset local et quel dépôt HF est
configuré.

### Les pages

| Page | Ce qu'elle fait |
|---|---|
| **1 · Collecter** | Upload d'une vidéo (`mp4`, `avi`, `mov`, `mkv`, `m4v`, `ts`, jusqu'à 20 Go) ou téléchargement YouTube via yt-dlp (1080p max par défaut). La vidéo est écrite par blocs de 8 Mo pour ne pas saturer la RAM, puis déplacée dans le dataset. |
| **2 · Analyser** | Envoie une vidéo au statut `raw` à l'API KyberIA, suit le job, puis rapatrie le CSV et la vidéo annotée. L'entrée passe alors au statut `analyzed`. |
| **3 · Dataset** | Statistiques, liste des entrées, aperçu du CSV (200 premières lignes), trajectoire du ballon, répartition `JEU` / `NON_JEU`, nombre de contacts détectés. |
| **4 · Publier** | Envoie les entrées `analyzed` sélectionnées sur le Hub, avec `metadata.json` et une carte de dataset (`README.md`) générée automatiquement. Le dépôt est créé **en privé** s'il n'existe pas. |

### Ajouter une vidéo en ligne de commande

Pour les très gros fichiers ou les ajouts en lot, on peut se passer de
l'interface :

```bash
uv run scripts/add_local_video.py /chemin/vers/match.mp4 --source "Ligue A J5"
```

| Option | Effet |
|---|---|
| `--source` | Description de la vidéo (par défaut : son chemin) |
| `--entry-id` | Identifiant de l'entrée (par défaut : horodatage `AAAAMMJJ_HHMMSS`) |
| `--move` | Déplace le fichier au lieu de le copier |

## Structure du dataset local

```
data/
├── uploads/                 # zone de transit (upload, YouTube)
└── dataset/
    ├── metadata.json        # index de toutes les entrées et de leur statut
    └── videos/
        └── {entry_id}/
            ├── raw.mp4          # vidéo d'origine
            ├── meta.json        # source, durée, résolution, fps, codec…
            ├── analysis.csv     # sortie KyberIA (après analyse)
            └── analyzed.mp4     # vidéo annotée (après analyse)
```

Cette arborescence est reproduite telle quelle sur le Hub.

### Colonnes de `analysis.csv`

Elles sont produites par le pipeline KyberIA :

| Colonne | Description |
|---|---|
| `frame`, `time_sec` | Numéro de l'image, temps en secondes |
| `ball_present` | Ballon détecté (0/1) |
| `x`, `y`, `confidence` | Position brute et score de TrackNet |
| `game_state`, `state_reason` | `JEU` / `NON_JEU` et règle qui a décidé |
| `smooth_x`, `smooth_y` | Position lissée (Savitzky-Golay) |
| `angle`, `direction` | Angle et direction de la trajectoire |
| `traj_change` | Changement de direction brusque, utilisé comme approximation d'un contact joueur-ballon |

## Organisation du code

```
app.py                  # page d'accueil
pages/                  # les 4 étapes (Streamlit multipage)
src/
├── config.py           # chemins, variables d'environnement, taille des blocs
├── collect.py          # upload par blocs, yt-dlp, ffprobe
├── transform.py        # KyberiaClient : client HTTP de l'API KyberIA
├── storage.py          # DatasetStore : dataset local + carte HF
└── publish.py          # HFPublisher : envoi vers le Hub
scripts/
└── add_local_video.py  # ajout d'une vidéo en ligne de commande
```

## Limites connues

- **Le client API ne correspond pas à l'API KyberIA actuelle.**
  `src/transform.py` appelle des routes et des noms de champ qui n'existent
  pas côté API :

  | `KyberiaClient` | API KyberIA (`api/main.py`) |
  |---|---|
  | `POST /analyze`, champ `video` | `POST /upload`, champ `file` |
  | `GET /jobs/{id}` | `GET /status/{id}` |

  `/health`, `/csv/{id}` et `/video/{id}` sont corrects. Tant que ces deux
  appels ne sont pas corrigés, l'analyse échoue avec une erreur 404.
- **Taille maximale côté API : 500 Mo** (`MAX_SIZE_MB` dans `api/main.py`).
  La collecte accepte jusqu'à 20 Go, mais une vidéo de match complète sera
  refusée à l'analyse. De plus, l'API charge tout le fichier en mémoire
  (`await file.read()`).
- **Les vidéos ne sont pas ignorées par git.** `data/` contient des fichiers
  de plusieurs centaines de Mo. Ajouter `data/**/*.mp4` et
  `data/dataset/metadata.json` au `.gitignore` avant tout `git add .`.
- **Droits sur les vidéos.** Les matchs FFVB ne sont pas diffusables : ne pas
  les publier dans un dépôt public. La carte de dataset générée annonce une
  licence `cc-by-4.0`, à vérifier au cas par cas selon la source.
- La publication envoie un commit par fichier. Pour beaucoup d'entrées,
  `HfApi.upload_folder` ou `create_commit` regrouperait tout en un seul commit.
