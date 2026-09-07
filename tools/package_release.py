"""Create deterministic, self-contained GitHub release archives under 2 GiB."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

SUPPORT_FILES = ("Install-Fisher4K.ps1", "Restore-Fisher4K.ps1", "README.md", "RELEASE_NOTES.md")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def partitions(entries: list[dict], limit: int) -> list[list[dict]]:
    groups, current, size = [], [], 0
    for entry in entries:
        if entry["patch_size"] > limit:
            raise ValueError(f"A single patch exceeds archive limit: {entry['patch']}")
        if current and size + entry["patch_size"] > limit:
            groups.append(current)
            current, size = [], 0
        current.append(entry)
        size += entry["patch_size"]
    if current:
        groups.append(current)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=1900 * 1024 * 1024)
    args = parser.parse_args()
    source, output = args.input.resolve(), args.output.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    groups = partitions(manifest["species"], args.max_bytes)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for number, entries in enumerate(groups, 1):
        part_manifest = {**manifest, "bundle_count": len(entries), "species": entries,
                         "release_part": number, "release_part_count": len(groups)}
        name = f"FisherOnline-4K-Fish-Textures-v{manifest['version']}-part{number:02d}-of{len(groups):02d}.zip"
        archive_path = output / name
        with tempfile.TemporaryDirectory(dir=output) as temp_name:
            temp = Path(temp_name)
            (temp / "patches").mkdir()
            for filename in SUPPORT_FILES:
                (temp / filename).write_bytes((source / filename).read_bytes())
            (temp / "manifest.json").write_text(json.dumps(part_manifest, indent=2) + "\n", encoding="utf-8")
            for entry in entries:
                destination = temp / entry["patch"]
                destination.write_bytes((source / entry["patch"]).read_bytes())
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                for path in sorted(temp.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(temp).as_posix())
        digest = sha256(archive_path)
        archive_path.with_suffix(archive_path.suffix + ".sha256").write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
        if archive_path.stat().st_size >= 2 * 1024 * 1024 * 1024:
            raise RuntimeError(f"GitHub release asset limit exceeded: {archive_path.name}")
        records.append({"asset": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": digest,
                        "bundles": len(entries)})
    (output / f"FisherOnline-4K-Fish-Textures-v{manifest['version']}-assets.json").write_text(
        json.dumps({"version": manifest["version"], "max_archive_bytes": args.max_bytes, "assets": records}, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"status": "packaged", "version": manifest["version"], "archives": records}, indent=2))


if __name__ == "__main__":
    main()
