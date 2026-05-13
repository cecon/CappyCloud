"""Storage de anexos em filesystem local (volume Docker).

Layout: ``{base_dir}/{conversation_id}/{uuid}{ext}``.

Adapter cumpre :class:`AttachmentStorage`. Para produção em multi-host,
substituir por um S3 (ou afim) que implemente o mesmo port — o restante do
código não muda.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

from app.ports.services import AttachmentStorage

_SAFE_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _ext_from(filename: str, mime_type: str) -> str:
    _, dot, raw = filename.rpartition(".")
    if dot and 1 <= len(raw) <= 5 and raw.isalnum():
        return f".{raw.lower()}"
    return _SAFE_EXT.get(mime_type.lower(), ".bin")


class LocalVolumeAttachmentStorage(AttachmentStorage):
    """Persistência em volume montado no container da API.

    Cria o diretório base na primeira escrita; é seguro mesmo se o volume
    estiver vazio. Não lança quando o ficheiro a apagar não existe.
    """

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)

    async def save(self, *, conversation_id: str, filename: str, content: bytes) -> str:
        target_dir = self._base / conversation_id
        ext = _ext_from(filename, "")
        # ``filename`` original pode trazer mime no path; melhor lookup via
        # ext explícita quando o caller souber. Aqui só fallback.
        att_id = uuid.uuid4().hex
        target_path = target_dir / f"{att_id}{ext}"

        def _write() -> None:
            target_dir.mkdir(parents=True, exist_ok=True)
            with target_path.open("wb") as fh:
                fh.write(content)

        await asyncio.to_thread(_write)
        return str(target_path)

    async def read(self, storage_path: str) -> bytes:
        def _read() -> bytes:
            with open(storage_path, "rb") as fh:
                return fh.read()

        return await asyncio.to_thread(_read)

    async def delete(self, storage_path: str) -> bool:
        def _del() -> bool:
            try:
                os.remove(storage_path)
                return True
            except FileNotFoundError:
                return False

        return await asyncio.to_thread(_del)
