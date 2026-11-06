"""
Collecte — étape 1 du pipeline.
Deux sources : upload de fichier local, téléchargement YouTube via yt-dlp.
"""
import json
import subprocess
from pathlib import Path
from typing import Callable, Optional

from .config import CHUNK_SIZE


def save_uploaded_file(
        file_obj,
        output_dir: Path,
        filename: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
) -> Path:
    """
    Sauvegarde un UploadedFile Streamlit par blocs pour limiter la RAM.
    Pour les vidéos volumineuses (3h15 ≈ 11 Go), un seul read() saturerait.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / filename
    written = 0

    with open(dest, "wb") as f:
        while True:
            chunk = file_obj.read(CHUNK_SIZE)
            if not chunk:
                break
            f.write(chunk)
            written += len(chunk)
            if on_progress:
                on_progress(written, -1)

    return dest


def download_youtube(
        url: str,
        output_dir: Path,
        quality: str = "best[height<=1080]",
        on_line: Optional[Callable[[str], None]] = None,
) -> Path:
    """
    Télécharge une vidéo publique via yt-dlp et retourne son chemin.
    Utilise --merge-output-format mp4 pour garantir un conteneur compatible.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Récupérer le titre pour nommer le fichier
    info_proc = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", url],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(info_proc.stdout)
    raw_title = info.get("title", "video")
    safe = "".join(c for c in raw_title if c.isalnum() or c in " -_").strip()[:80]

    template = str(output_dir / f"{safe}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", quality,
        "--merge-output-format", "mp4",
        "-o", template,
        "--no-playlist",
        "--newline",
        url,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: list[str] = []
    for line in proc.stdout:
        line = line.strip()
        lines.append(line)
        if on_line:
            on_line(line)
    proc.wait()

    if proc.returncode != 0:
        raise RuntimeError("yt-dlp a échoué :\n" + "\n".join(lines[-15:]))

    # Localiser le fichier produit
    for f in sorted(output_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.suffix == ".mp4" and safe[:20] in f.stem:
            return f

    raise FileNotFoundError(f"Fichier téléchargé introuvable dans {output_dir}")


def get_video_metadata(path: Path) -> dict:
    """
    Extrait durée, résolution, codec via ffprobe.
    Retourne un dict vide sur les machines sans ffprobe.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # ffprobe absent du PATH : on dégrade proprement au lieu de planter
        return {"size_bytes": path.stat().st_size}
    if result.returncode != 0:
        return {"size_bytes": path.stat().st_size}

    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    duration_s = float(fmt.get("duration", 0))
    size_bytes = int(fmt.get("size", path.stat().st_size))

    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        {},
    )

    try:
        num, den = video_stream.get("r_frame_rate", "0/1").split("/")
        fps = round(int(num) / int(den), 2) if int(den) else 0
    except (ValueError, ZeroDivisionError):
        fps = 0

    h = int(duration_s // 3600)
    m = int((duration_s % 3600) // 60)
    s = int(duration_s % 60)

    return {
        "duration_seconds": round(duration_s, 1),
        "duration_human": f"{h}h{m:02d}m{s:02d}s",
        "size_bytes": size_bytes,
        "size_human": f"{size_bytes / (1024 ** 3):.2f} Go",
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": fps,
        "codec": video_stream.get("codec_name"),
    }

