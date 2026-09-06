"""Build redistributable, version-locked patches from verified local bundles.

The output contains only compressed replacement blocks and hashes. Original
Fisher Online bundles are never copied into the release.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path


MAGIC = b"F4KP1\0"
BLOCK_SIZE = 1024 * 1024
STAMP = re.compile(r"(\d{8}-\d{6})")

SPECIES = {
    "fishs_assets_fishingame_598_mfox.bundle": "Sea Fox",
    "fishs_assets_fishingame_392_zubatka.bundle": "Wolffish",
    "fishs_assets_fishingame_538_haddy.bundle": "Haddock",
    "fishs_assets_fishingame_562_marlin.bundle": "Blue Marlin",
    "fishs_assets_fishingame_2_ukleya.bundle": "Bleak",
    "fishs_assets_fishingame_4_okun.bundle": "Perch",
    "fishs_assets_fishingame_601_forelbalkanbig.bundle": "Balkan Trout - Large",
    "fishs_assets_fishingame_601_forelbalkanmed.bundle": "Balkan Trout - Trophy",
    "fishs_assets_fishingame_601_forelbalkansmall.bundle": "Balkan Trout - Normal",
    "fishs_assets_fishingame_101_rog.bundle": "Siberian Sculpin",
    "fishs_assets_fishingame_106_taimen.bundle": "Taimen",
    "fishs_assets_fishingame_111_ugor.bundle": "European Eel",
    "fishs_assets_fishingame_11_som.bundle": "Wels Catfish",
    "fishs_assets_fishingame_12_golavl.bundle": "Common Chub",
    "fishs_assets_fishingame_142_gol.bundle": "Lake Minnow",
    "fishs_assets_fishingame_14_vobla.bundle": "Vobla",
    "fishs_assets_fishingame_16_carp.bundle": "Common Carp - Large and Trophy",
    "fishs_assets_fishingame_16_carp_small.bundle": "Common Carp - Normal",
    "fishs_assets_fishingame_16_viun.bundle": "European Weatherfish",
    "fishs_assets_fishingame_17_sudak.bundle": "Zander",
    "fishs_assets_fishingame_18_carp_smallmirror.bundle": "Mirror Carp - Normal",
    "fishs_assets_fishingame_18_carpmirror.bundle": "Mirror Carp - Large and Trophy",
    "fishs_assets_fishingame_1_crucian.bundle": "Crucian Carp",
    "fishs_assets_fishingame_304_dtaimen.bundle": "Danube Taimen",
    "fishs_assets_fishingame_30_malek.bundle": "Juvenile Bleak",
    "fishs_assets_fishingame_31_perch.bundle": "Percarina",
    "fishs_assets_fishingame_409_podust.bundle": "Common Nase",
    "fishs_assets_fishingame_5_perch.bundle": "Ruffe",
    "fishs_assets_fishingame_6_beluga.bundle": "Beluga",
    "fishs_assets_fishingame_7_yaz.bundle": "Ide",
    "fishs_assets_fishingame_8_peskar.bundle": "Gudgeon",
    "fishs_assets_fishingame_91_sazan.bundle": "Wild Carp - Normal",
    "fishs_assets_fishingame_91_sazan_big.bundle": "Wild Carp - Large and Trophy",
    "fishs_assets_fishingame_9_bream.bundle": "Common Bream",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_time(path: Path) -> datetime:
    match = STAMP.search(path.parent.name)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%d-%H%M%S")
    return datetime.max


def earliest_backup(backup_root: Path, bundle: str) -> Path:
    candidates = sorted(backup_root.rglob(bundle), key=backup_time)
    if not candidates:
        raise FileNotFoundError(f"No rollback source found for {bundle}")
    return candidates[0]


def write_patch(source: Path, target: Path, output: Path) -> dict:
    source_size = source.stat().st_size
    target_size = target.stat().st_size
    source_hash = bytes.fromhex(sha256(source))
    target_hash = bytes.fromhex(sha256(target))
    output.parent.mkdir(parents=True, exist_ok=True)
    changed = 0
    raw_changed = 0
    with source.open("rb") as before, target.open("rb") as after, output.open("wb") as patch:
        patch.write(MAGIC)
        patch.write(struct.pack("<QQ", source_size, target_size))
        patch.write(source_hash)
        patch.write(target_hash)
        patch.write(struct.pack("<II", BLOCK_SIZE, 0))
        while True:
            offset = after.tell()
            target_block = after.read(BLOCK_SIZE)
            if not target_block:
                break
            source_block = before.read(BLOCK_SIZE)
            if target_block != source_block:
                compressed = gzip.compress(target_block, compresslevel=9, mtime=0)
                patch.write(struct.pack("<QII", offset, len(target_block), len(compressed)))
                patch.write(compressed)
                changed += 1
                raw_changed += len(target_block)
        patch.seek(len(MAGIC) + 16 + 64 + 4)
        patch.write(struct.pack("<I", changed))
    return {
        "source_size": source_size,
        "target_size": target_size,
        "source_sha256": source_hash.hex(),
        "target_sha256": target_hash.hex(),
        "patch_size": output.stat().st_size,
        "patch_sha256": sha256(output),
        "changed_blocks": changed,
        "raw_changed_bytes": raw_changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="0.1.0")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    game_root = args.game_root.resolve()
    live_root = game_root / "theFisher_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64"
    backups = game_root / "Mod Backups"
    coverage = json.loads((workspace / "artifacts" / "fish-fidelity-catalog" / "coverage.json").read_text())
    verified = sorted(row["bundle"] for row in coverage["queue"] if row["verified_local_upgrade"])
    if set(verified) != set(SPECIES):
        raise RuntimeError(f"Species map mismatch: missing={set(verified)-set(SPECIES)}, extra={set(SPECIES)-set(verified)}")

    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    patches = output / "patches"
    patches.mkdir(parents=True)
    entries = []
    by_bundle = {row["bundle"]: row for row in coverage["queue"]}
    for index, bundle in enumerate(verified, 1):
        source = earliest_backup(backups, bundle)
        target = live_root / bundle
        if sha256(source) == sha256(target):
            raise RuntimeError(f"Verified bundle has no binary delta: {bundle}")
        patch_path = patches / f"{bundle}.f4kp"
        stats = write_patch(source, target, patch_path)
        row = by_bundle[bundle]
        entries.append({
            "species": SPECIES[bundle],
            "bundle": bundle,
            "patch": f"patches/{patch_path.name}",
            "textures": {
                "color": [item["name"] for item in row["color_textures"]],
                "normal": [item["name"] for item in row["normal_textures"]],
            },
            **stats,
        })
        print(f"[{index:02d}/{len(verified)}] {SPECIES[bundle]}: {stats['patch_size']/1048576:.1f} MiB")

    manifest = {
        "format": "F4KP1",
        "version": args.version,
        "game": "Fisher Online",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bundle_count": len(entries),
        "species": entries,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": args.version,
        "bundles": len(entries),
        "patch_bytes": sum(item["patch_size"] for item in entries),
        "output": str(output),
    }, indent=2))


if __name__ == "__main__":
    main()
