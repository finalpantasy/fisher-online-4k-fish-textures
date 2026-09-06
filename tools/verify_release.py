"""Reconstruct every release target from its rollback source and verify SHA-256."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import struct
import tempfile
from pathlib import Path

from build_release import MAGIC, earliest_backup


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def apply_patch(source: Path, patch: Path, output: Path) -> None:
    shutil.copy2(source, output)
    with patch.open("rb") as encoded, output.open("r+b") as target:
        if encoded.read(len(MAGIC)) != MAGIC:
            raise ValueError(f"Invalid patch magic: {patch}")
        source_size, target_size = struct.unpack("<QQ", encoded.read(16))
        source_hash = encoded.read(32).hex()
        target_hash = encoded.read(32).hex()
        block_size, count = struct.unpack("<II", encoded.read(8))
        if source_size != source.stat().st_size or source_hash != sha256(source):
            raise ValueError(f"Source metadata mismatch: {source.name}")
        target.truncate(target_size)
        for _ in range(count):
            offset, raw_size, compressed_size = struct.unpack("<QII", encoded.read(16))
            if raw_size > block_size or offset + raw_size > target_size:
                raise ValueError(f"Invalid block bounds: {patch.name}")
            raw = gzip.decompress(encoded.read(compressed_size))
            if len(raw) != raw_size:
                raise ValueError(f"Invalid block length: {patch.name}")
            target.seek(offset)
            target.write(raw)
        if encoded.read(1):
            raise ValueError(f"Trailing patch data: {patch.name}")
    if sha256(output) != target_hash:
        raise ValueError(f"Reconstructed hash mismatch: {source.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--game-root", type=Path, required=True)
    args = parser.parse_args()
    release = args.release.resolve()
    backup_root = args.game_root.resolve() / "Mod Backups"
    manifest = json.loads((release / "manifest.json").read_text())
    with tempfile.TemporaryDirectory(dir=release) as temporary:
        temp = Path(temporary)
        for index, entry in enumerate(manifest["species"], 1):
            source = earliest_backup(backup_root, entry["bundle"])
            patch = release / entry["patch"]
            if sha256(patch) != entry["patch_sha256"]:
                raise ValueError(f"Patch hash mismatch: {patch.name}")
            output = temp / entry["bundle"]
            apply_patch(source, patch, output)
            if sha256(output) != entry["target_sha256"]:
                raise ValueError(f"Manifest target mismatch: {entry['bundle']}")
            output.unlink()
            print(f"[{index:02d}/{len(manifest['species'])}] verified {entry['species']}")
    print(json.dumps({"status": "verified", "bundles": len(manifest["species"]), "version": manifest["version"]}))


if __name__ == "__main__":
    main()
