from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from app.config import get_settings

settings = get_settings()


class StorageProvider(Protocol):
    def save(self, case_id: str, evidence_id: str, filename: str, data: bytes) -> str: ...
    def load(self, path: str) -> bytes | None: ...
    def exists(self, path: str) -> bool: ...
    def delete(self, path: str) -> None: ...
    def label(self) -> str: ...


class LocalStorageProvider:
    """Stores files under {DATA_DIR}/uploads/{case_id}/. DEV default."""

    def __init__(self) -> None:
        self.root = settings.uploads_path

    def _resolve(self, path: str) -> Path | None:
        """Resolve `path` against the storage root, rejecting escapes.

        Returns None when the resolved candidate (absolute path, `../`
        traversal or symlink target) falls outside the storage root.
        """
        root = self.root.resolve()
        # os.path.join discards root for absolute paths; the resolve+containment
        # check below catches that case along with traversal and symlink escapes.
        resolved = Path(os.path.join(root, path)).resolve()
        if not resolved.is_relative_to(root):
            return None
        return resolved

    def save(self, case_id: str, evidence_id: str, filename: str, data: bytes) -> str:
        root = self.root.resolve()
        folder = self._resolve(case_id)
        if folder is None:
            raise ValueError(f"path escapes storage root: {case_id}")
        folder.mkdir(parents=True, exist_ok=True)
        safe = Path(filename).name or evidence_id
        target = folder / f"{evidence_id}__{safe}"
        target.write_bytes(data)
        return str(target.relative_to(root))

    def load(self, path: str) -> bytes | None:
        p = self._resolve(path)
        if p is None:
            return None
        return p.read_bytes() if p.exists() else None

    def exists(self, path: str) -> bool:
        p = self._resolve(path)
        return p is not None and p.exists()

    def delete(self, path: str) -> None:
        p = self._resolve(path)
        if p is None:
            raise ValueError(f"path escapes storage root: {path}")
        p.unlink(missing_ok=True)

    def label(self) -> str:
        return "local"


class FirebaseStorageProvider:
    """Optional Firebase Storage adapter. Requires firebase-admin configured."""

    def __init__(self) -> None:
        from firebase_admin import credentials, initialize_app, storage  # noqa: F401

        self._ready = False
        if settings.FIREBASE_CREDENTIAL_PATH:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIAL_PATH)
            initialize_app(cred, {"storageBucket": settings.FIREBASE_STORAGE_BUCKET})
            self._ready = True

    def label(self) -> str:
        return "firebase"

    def save(self, case_id: str, evidence_id: str, filename: str, data: bytes) -> str:
        if not self._ready:
            raise RuntimeError("Firebase storage not configured")
        from firebase_admin import storage

        bucket = storage.bucket()
        blob = bucket.blob(f"bakke/{case_id}/{evidence_id}/{filename}")
        blob.upload_from_string(data)
        return f"gs://bakke/{case_id}/{evidence_id}/{filename}"

    def load(self, path: str) -> bytes | None:
        if not self._ready:
            return None
        from firebase_admin import storage

        bucket = storage.bucket()
        blob = bucket.blob(path.replace("gs://", "", 1))
        return blob.download_as_bytes() if blob.exists() else None

    def exists(self, path: str) -> bool:
        if not self._ready:
            return False
        from firebase_admin import storage

        blob = storage.bucket().blob(path.replace("gs://", "", 1))
        return blob.exists()

    def delete(self, path: str) -> None:
        if not self._ready:
            return
        from firebase_admin import storage

        storage.bucket().blob(path.replace("gs://", "", 1)).delete()


def get_storage_provider() -> StorageProvider:
    if settings.STORAGE_PROVIDER == "firebase":
        return FirebaseStorageProvider()
    return LocalStorageProvider()