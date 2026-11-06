"""
Publication — étape 4 du pipeline.
Upload du dataset local vers HuggingFace Hub (ynov/kyberia-data).
"""
from pathlib import Path
from typing import Callable, Optional

from huggingface_hub import HfApi, create_repo
from huggingface_hub.utils import RepositoryNotFoundError

from .storage import DatasetStore


class HFPublisher:
    """Publie le DatasetStore local sur HuggingFace Hub."""

    def __init__(self, token: str, repo_id: str):
        self.repo_id = repo_id
        self.token = token
        self.api = HfApi(token=token)

    def ensure_repo(self) -> str:
        """Crée le dépôt dataset s'il n'existe pas encore."""
        try:
            info = self.api.repo_info(repo_id=self.repo_id, repo_type="dataset")
            return info.id
        except RepositoryNotFoundError:
            return create_repo(
                repo_id=self.repo_id,
                token=self.token,
                repo_type="dataset",
                private=True,
                exist_ok=True,
            )

    def _upload(self, local: Path, remote: str, msg: str):
        self.api.upload_file(
            path_or_fileobj=str(local),
            path_in_repo=remote,
            repo_id=self.repo_id,
            repo_type="dataset",
            token=self.token,
            commit_message=msg,
        )

    def upload_entry(
        self,
        store: DatasetStore,
        entry_id: str,
        on_file: Optional[Callable[[str, int, int], None]] = None,
    ):
        """Upload tous les fichiers d'une entrée."""
        entry_dir = store.root / "videos" / entry_id
        files = [f for f in entry_dir.iterdir() if f.is_file()]

        for i, f in enumerate(files):
            if on_file:
                on_file(f.name, i + 1, len(files))
            self._upload(f, f"videos/{entry_id}/{f.name}", f"Add {entry_id}/{f.name}")

    def upload_all(
        self,
        store: DatasetStore,
        entry_ids: Optional[list[str]] = None,
        on_entry: Optional[Callable[[str, int, int], None]] = None,
    ):
        """
        Upload l'ensemble du dataset (ou une liste d'entrées spécifiques).
        Idempotent : HF Hub écrase les fichiers existants.
        """
        entries = store.get_entries()
        if entry_ids:
            entries = [e for e in entries if e["entry_id"] in entry_ids]

        for i, entry in enumerate(entries):
            eid = entry["entry_id"]
            if on_entry:
                on_entry(eid, i + 1, len(entries))
            self.upload_entry(store, eid)

        # Fichiers globaux
        self._upload(store._meta_path, "metadata.json", "Update metadata index")
        self.api.upload_file(
            path_or_fileobj=store.dataset_card().encode("utf-8"),
            path_in_repo="README.md",
            repo_id=self.repo_id,
            repo_type="dataset",
            token=self.token,
            commit_message="Update dataset card",
        )
