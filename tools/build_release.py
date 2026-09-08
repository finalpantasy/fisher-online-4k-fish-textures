"""Build a public, journal-backed Fisher Online texture release.

Only inventory entries whose current live hash matches a successful
``installed_and_readback_verified`` journal are released. Original game
bundles are never copied into the output; patches contain only replacement
blocks and the precise pre-install and live SHA-256 values.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path

MAGIC = b"F4KP1\0"
BLOCK_SIZE = 1024 * 1024

# Catalog/journal identifiers are authoritative for inclusion. These labels
# are release-facing only; identity is never inferred from serialized names.
SPECIES = {
    "fishs_assets_fishingame_007_amur.bundle": "Grass Carp",
    "fishs_assets_fishingame_101_rog.bundle": "Siberian Sculpin",
    "fishs_assets_fishingame_103_sterl.bundle": "Sterlet",
    "fishs_assets_fishingame_106_taimen.bundle": "Taimen",
    "fishs_assets_fishingame_110_giantpike.bundle": "Giant Pike",
    "fishs_assets_fishingame_111_ugor.bundle": "European Eel",
    "fishs_assets_fishingame_116_harius.bundle": "Grayling",
    "fishs_assets_fishingame_11_som.bundle": "Wels Catfish",
    "fishs_assets_fishingame_121_amurblack.bundle": "Black Grass Carp",
    "fishs_assets_fishingame_123_chehon.bundle": "Sabrefish",
    "fishs_assets_fishingame_128_bigpike.bundle": "Giant Pike - Large",
    "fishs_assets_fishingame_128_grasspike.bundle": "Grass Pike",
    "fishs_assets_fishingame_12_golavl.bundle": "Common Chub",
    "fishs_assets_fishingame_136_forelgold.bundle": "Golden Trout",
    "fishs_assets_fishingame_142_gol.bundle": "Lake Minnow",
    "fishs_assets_fishingame_14_vobla.bundle": "Vobla",
    "fishs_assets_fishingame_16_carp.bundle": "Common Carp - Large and Trophy",
    "fishs_assets_fishingame_16_carp_small.bundle": "Common Carp - Normal",
    "fishs_assets_fishingame_16_viun.bundle": "European Weatherfish",
    "fishs_assets_fishingame_17_sudak.bundle": "Zander",
    "fishs_assets_fishingame_18_carp_smallmirror.bundle": "Mirror Carp - Normal",
    "fishs_assets_fishingame_18_carpmirror.bundle": "Mirror Carp - Large and Trophy",
    "fishs_assets_fishingame_1_crucian.bundle": "Crucian Carp",
    "fishs_assets_fishingame_209_osetratlantic.bundle": "Atlantic Sturgeon",
    "fishs_assets_fishingame_21_golecarct.bundle": "Arctic Char",
    "fishs_assets_fishingame_27_golec.bundle": "Stone Loach",
    "fishs_assets_fishingame_2_ukleya.bundle": "Bleak",
    "fishs_assets_fishingame_28_elec.bundle": "Dace",
    "fishs_assets_fishingame_304_dtaimen.bundle": "Danube Taimen",
    "fishs_assets_fishingame_30_malek.bundle": "Juvenile Bleak",
    "fishs_assets_fishingame_31_perch.bundle": "Percarina",
    "fishs_assets_fishingame_32_minog.bundle": "Siberian Lamprey",
    "fishs_assets_fishingame_33_gereh.bundle": "Asp",
    "fishs_assets_fishingame_339_altufa.bundle": "Altufa",
    "fishs_assets_fishingame_353_terpg.bundle": "Black Cod",
    "fishs_assets_fishingame_363_perchstrip.bundle": "Striped Ruffe",
    "fishs_assets_fishingame_372_seld.bundle": "Baltic Herring",
    "fishs_assets_fishingame_375_paltus.bundle": "Atlantic Halibut",
    "fishs_assets_fishingame_382_hake.bundle": "European Hake",
    "fishs_assets_fishingame_385_chinuk.bundle": "Chinook Salmon",
    "fishs_assets_fishingame_389_squid.bundle": "Squid",
    "fishs_assets_fishingame_392_zubatka.bundle": "Wolffish",
    "fishs_assets_fishingame_402_sshark.bundle": "Spiny Dogfish",
    "fishs_assets_fishingame_401_nerka.bundle": "Sockeye Salmon",
    "fishs_assets_fishingame_409_podust.bundle": "Common Nase",
    "fishs_assets_fishingame_411_gar.bundle": "Longnose Gar",
    "fishs_assets_fishingame_413_nudecarp.bundle": "Leather Carp",
    "fishs_assets_fishingame_441_snake.bundle": "Taiwan Loach",
    "fishs_assets_fishingame_447_vostro.bundle": "Sharpbelly",
    "fishs_assets_fishingame_449_bream.bundle": "Black Bream",
    "fishs_assets_fishingame_452_kosatka.bundle": "Kosatka",
    "fishs_assets_fishingame_46_kor.bundle": "Japanese Smelt",
    "fishs_assets_fishingame_464_marinka.bundle": "Sattar Snowtrout",
    "fishs_assets_fishingame_475_osman.bundle": "Osman",
    "fishs_assets_fishingame_478_forel.bundle": "Trout",
    "fishs_assets_fishingame_481_osman.bundle": "Scaly Osman",
    "fishs_assets_fishingame_488_snetok.bundle": "Smelt",
    "fishs_assets_fishingame_499_viun.bundle": "Siberian Stone Loach",
    "fishs_assets_fishingame_4_okun.bundle": "Perch",
    "fishs_assets_fishingame_503_iceviun.bundle": "Ice Loach",
    "fishs_assets_fishingame_506_puzanok.bundle": "Puzanok / Danube Shad",
    "fishs_assets_fishingame_50_forelradug.bundle": "Rainbow Trout",
    "fishs_assets_fishingame_511_osetrwhite.bundle": "White Sturgeon",
    "fishs_assets_fishingame_527_blue.bundle": "Bluefish",
    "fishs_assets_fishingame_529_allis.bundle": "Allis Shad",
    "fishs_assets_fishingame_533_marbletrout.bundle": "Marble Trout",
    "fishs_assets_fishingame_534_somalb.bundle": "Albino Wels Catfish",
    "fishs_assets_fishingame_535_tresk.bundle": "Atlantic Cod - Normal",
    "fishs_assets_fishingame_535_tresk_big.bundle": "Atlantic Cod - Large",
    "fishs_assets_fishingame_538_haddy.bundle": "Haddock",
    "fishs_assets_fishingame_54_lin.bundle": "Tench",
    "fishs_assets_fishingame_551_catfishblue.bundle": "Blue Catfish",
    "fishs_assets_fishingame_553_koi.bundle": "Koi - Large and Trophy",
    "fishs_assets_fishingame_553_koi_small.bundle": "Koi - Normal",
    "fishs_assets_fishingame_558_icyharius.bundle": "Icy Grayling",
    "fishs_assets_fishingame_55_salmon.bundle": "Atlantic Salmon",
    "fishs_assets_fishingame_562_marlin.bundle": "Blue Marlin",
    "fishs_assets_fishingame_563_pelam.bundle": "Atlantic Bonito",
    "fishs_assets_fishingame_564_konger.bundle": "Conger Eel",
    "fishs_assets_fishingame_597_tuna.bundle": "Yellowfin Tuna - Striped",
    "fishs_assets_fishingame_598_mfox.bundle": "Sea Fox",
    "fishs_assets_fishingame_5_perch.bundle": "Ruffe",
    "fishs_assets_fishingame_601_forelbalkanbig.bundle": "Balkan Trout - Large",
    "fishs_assets_fishingame_601_forelbalkanmed.bundle": "Balkan Trout - Trophy",
    "fishs_assets_fishingame_601_forelbalkansmall.bundle": "Balkan Trout - Normal",
    "fishs_assets_fishingame_603_goblinshark.bundle": "Goblin Shark",
    "fishs_assets_fishingame_61_nalim.bundle": "Burbot",
    "fishs_assets_fishingame_65_forelpond.bundle": "Pond Trout",
    "fishs_assets_fishingame_6_beluga.bundle": "Beluga",
    "fishs_assets_fishingame_74_palia.bundle": "Brook Charr",
    "fishs_assets_fishingame_7_yaz.bundle": "Ide",
    "fishs_assets_fishingame_8_peskar.bundle": "Gudgeon",
    "fishs_assets_fishingame_91_sazan.bundle": "Wild Carp - Normal",
    "fishs_assets_fishingame_91_sazan_big.bundle": "Wild Carp - Large and Trophy",
    "fishs_assets_fishingame_9_bassblack.bundle": "Largemouth Bass",
    "fishs_assets_fishingame_9_bream.bundle": "Common Bream",
}
SCIENTIFIC_NAMES = {"fishs_assets_fishingame_74_palia.bundle": "Salvelinus fontinalis"}
PRISTINE_OVERRIDES = {
    "fishs_assets_fishingame_409_podust.bundle": (
        "ef808ff06446e1af2ebfc743afe2799139acccca1a48ec4b9d164d078c9775ef",
        "common-nase-texture-trial-20260905/fishs_assets_fishingame_409_podust/original.bundle",
        "common-nase-texture-trial-20260905/repaint-v2/verification.json",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_journal_records(artifacts_root: Path) -> dict[str, list[dict]]:
    """Index every successful per-bundle before/after record by target name."""
    records: dict[str, list[dict]] = {}
    for journal_path in artifacts_root.rglob("installation.json"):
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Cannot read installation journal: {journal_path}") from error
        if journal.get("status") != "installed_and_readback_verified":
            continue
        if not journal.get("backup"):
            raise RuntimeError(f"Successful journal has no backup path: {journal_path}")
        for entry in journal.get("bundles") or [journal]:
            if not {"bundle", "before_sha256", "after_sha256"} <= set(entry):
                continue
            records.setdefault(entry["bundle"], []).append({
                "before_sha256": entry["before_sha256"],
                "after_sha256": entry["after_sha256"],
                "textures": entry.get("textures"),
                "backup": Path(journal["backup"]),
                "journal_path": journal_path,
            })
    return records


def iter_dicts(value):
    """Yield every dictionary in a decoded artifact document."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def load_retained_pristine_sources(artifacts_root: Path, bundles: set[str], journal_records: dict[str, list[dict]]) -> dict[str, dict]:
    """Find independently attested retained originals, never journal terminals.

    A source is eligible only when an artifact verification names it as an
    ``original_sha256`` for the exact bundle and a retained ``original.bundle``
    on disk hashes to that value.  This deliberately excludes journal backups:
    a backup can itself already be modded.
    """
    wanted: dict[str, list[tuple[str, Path]]] = {bundle: [] for bundle in bundles}
    for verification_path in artifacts_root.rglob("verification.json"):
        try:
            document = json.loads(verification_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for record in iter_dicts(document):
            bundle, original = record.get("bundle"), record.get("original_sha256")
            if bundle in wanted and isinstance(original, str) and len(original) == 64:
                wanted[bundle].append((original.lower(), verification_path))

    originals: dict[str, list[Path]] = {}
    for candidate in artifacts_root.rglob("original.bundle"):
        originals.setdefault(sha256(candidate), []).append(candidate)

    # Most package artifacts retain originals as ``originals/<bundle>``.  They
    # are authoritative only when the file agrees with the earliest successful
    # journal source; the separately verified Common Nase original above is
    # allowed to supersede an old trial journal terminal.
    retained_by_name: dict[str, list[Path]] = {bundle: [] for bundle in bundles}
    for bundle in bundles:
        retained_by_name[bundle] = [path for path in artifacts_root.rglob(bundle)
                                    if path.is_file() and path.parent.name.lower() == "originals"]

    resolved: dict[str, dict] = {}
    for bundle, proofs in wanted.items():
        if bundle in PRISTINE_OVERRIDES:
            digest, relative_source, relative_evidence = PRISTINE_OVERRIDES[bundle]
            source_path, evidence = artifacts_root / relative_source, artifacts_root / relative_evidence
            if not source_path.is_file() or sha256(source_path) != digest:
                raise RuntimeError(f"Pristine override source mismatch for {bundle}")
            resolved[bundle] = {"sha256": digest, "path": source_path, "verification": evidence,
                                "kind": "verification_attested_original"}
            continue
        matches = []
        for expected_hash, verification_path in proofs:
            for source in originals.get(expected_hash, []):
                # The artifact's parent chain must identify this exact bundle;
                # a same-hash unrelated original is not admissible evidence.
                if bundle in {path.name for path in source.parents} or bundle in str(source.parent):
                    matches.append((expected_hash, verification_path, source))
        unique = {(digest, path.resolve()) for digest, _, path in matches}
        if unique:
            # Identical retained copies are harmless; choose the stable first.
            expected_hash, source_path = sorted(unique, key=lambda item: str(item[1]))[0]
            evidence = next(path for digest, path, _ in matches if digest == expected_hash and _.resolve() == source_path)
            resolved[bundle] = {"sha256": expected_hash, "path": source_path, "verification": evidence,
                                "kind": "verification_attested_original"}
            continue
        roots = {record["before_sha256"] for record in journal_records.get(bundle, [])
                 if not any(other["after_sha256"] == record["before_sha256"] for other in journal_records.get(bundle, []))}
        retained = [path for path in retained_by_name[bundle] if sha256(path) in roots]
        if not retained:
            raise RuntimeError(f"No retained pristine original for {bundle}")
        if len({sha256(path) for path in retained}) != 1:
            raise RuntimeError(f"Ambiguous retained pristine originals for {bundle}")
        source_path = sorted(retained, key=str)[0]
        resolved[bundle] = {"sha256": sha256(source_path), "path": source_path, "verification": None,
                            "kind": "retained_originals_directory"}
    return resolved


def lineage_for(records: dict[str, list[dict]], bundle: str, live_hash: str) -> list[dict]:
    """Walk a unique successful journal chain from the live target to pristine."""
    chain_backwards: list[dict] = []
    current, seen = live_hash, set()
    while True:
        matches = [record for record in records.get(bundle, []) if record["after_sha256"] == current]
        if len(matches) != 1:
            raise RuntimeError(f"Unproven journal lineage for {bundle}: {len(matches)} records end at {current}")
        record = matches[0]
        if current in seen:
            raise RuntimeError(f"Cyclic journal lineage for {bundle}")
        seen.add(current)
        chain_backwards.append(record)
        current = record["before_sha256"]
        if not any(candidate["after_sha256"] == current for candidate in records.get(bundle, [])):
            return list(reversed(chain_backwards))


def record_textures(record: dict, bundle: str) -> list[dict]:
    """Obtain changed Texture2D evidence, including the one legacy journal fallback."""
    if record["textures"]:
        return record["textures"]
    verification_path = record["journal_path"].parent / "verification.json"
    try:
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No texture proof for {bundle}: {verification_path}") from error
    if (verification.get("status") != "offline_verified" or verification.get("bundle") != bundle
            or verification.get("before_sha256") != record["before_sha256"]
            or verification.get("after_sha256") != record["after_sha256"] or not verification.get("textures")):
        raise RuntimeError(f"Legacy texture proof does not match journal lineage for {bundle}")
    return verification["textures"]


def cumulative_textures(lineage: list[dict], bundle: str) -> tuple[dict[str, list[str]], list[int]]:
    """Return the cumulative changed Texture2D names and IDs across every step."""
    names = {"color": [], "normal": []}
    ids: list[int] = []
    seen_names, seen_ids = set(), set()
    for record in lineage:
        for texture in record_textures(record, bundle):
            key = (texture.get("id"), texture.get("name"))
            if key not in seen_names:
                kind = "normal" if texture.get("kind") == "normal" or "normal" in texture.get("name", "").lower() else "color"
                names[kind].append(texture["name"])
                seen_names.add(key)
            if isinstance(texture.get("id"), int) and texture["id"] not in seen_ids:
                ids.append(texture["id"])
                seen_ids.add(texture["id"])
    if not ids:
        raise RuntimeError(f"No cumulative changed Texture2D IDs proven for {bundle}")
    return names, ids


def write_patch(source: Path, target: Path, output: Path) -> dict:
    source_size, target_size = source.stat().st_size, target.stat().st_size
    source_hash, target_hash = bytes.fromhex(sha256(source)), bytes.fromhex(sha256(target))
    output.parent.mkdir(parents=True, exist_ok=True)
    changed = raw_changed = 0
    with source.open("rb") as before, target.open("rb") as after, output.open("wb") as patch:
        patch.write(MAGIC)
        patch.write(struct.pack("<QQ", source_size, target_size))
        patch.write(source_hash)
        patch.write(target_hash)
        patch.write(struct.pack("<II", BLOCK_SIZE, 0))
        while target_block := after.read(BLOCK_SIZE):
            offset, source_block = after.tell() - len(target_block), before.read(BLOCK_SIZE)
            if target_block != source_block:
                compressed = gzip.compress(target_block, compresslevel=9, mtime=0)
                patch.write(struct.pack("<QII", offset, len(target_block), len(compressed)))
                patch.write(compressed)
                changed += 1
                raw_changed += len(target_block)
        patch.seek(len(MAGIC) + 16 + 64 + 4)
        patch.write(struct.pack("<I", changed))
    return {"source_size": source_size, "target_size": target_size, "source_sha256": source_hash.hex(),
            "target_sha256": target_hash.hex(), "patch_size": output.stat().st_size,
            "patch_sha256": sha256(output), "changed_blocks": changed, "raw_changed_bytes": raw_changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    artifacts_root = args.inventory.resolve().parent.parent
    journal_records = load_journal_records(artifacts_root)
    live_root = args.game_root.resolve() / "theFisher_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64"
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    patches = output / "patches"
    entries = []
    candidates = sorted((row for row in inventory["bundles"] if row.get("has_verified_local_upgrade")), key=lambda row: row["bundle"])
    if len(candidates) != inventory.get("verified_upgrade_bundle_count"):
        raise RuntimeError("Inventory verified-upgrade count does not match its candidate rows")
    if set(row["bundle"] for row in candidates) != set(SPECIES):
        raise RuntimeError("Public species map does not cover the authoritative inventory exactly")
    pristine_sources = load_retained_pristine_sources(artifacts_root, set(SPECIES), journal_records)
    for index, row in enumerate(candidates, 1):
        bundle, live_hash = row["bundle"], row["sha256"]
        lineage = lineage_for(journal_records, bundle, live_hash)
        pristine = pristine_sources[bundle]
        source, target = pristine["path"], live_root / bundle
        if not source.is_file() or not target.is_file():
            raise FileNotFoundError(f"Missing verified source or live target for {bundle}")
        if sha256(source) != pristine["sha256"]:
            raise RuntimeError(f"Pristine backup SHA mismatch for {bundle}")
        if sha256(target) != live_hash:
            raise RuntimeError(f"Live SHA drift for {bundle}")
        patch = patches / f"{bundle}.f4kp"
        stats = write_patch(source, target, patch)
        if stats["target_sha256"] != live_hash:
            raise RuntimeError(f"Generated target SHA mismatch for {bundle}")
        textures, texture_ids = cumulative_textures(lineage, bundle)
        entry = {"species": SPECIES[bundle], "bundle": bundle, "patch": f"patches/{patch.name}",
                 "textures": textures, "changed_texture_ids": texture_ids,
                 "lineage_steps": [{"before_sha256": record["before_sha256"], "after_sha256": record["after_sha256"]}
                                   for record in lineage],
                 "pristine_evidence": {"kind": pristine["kind"], "sha256": pristine["sha256"],
                                       "verification_file": pristine["verification"].name if pristine["verification"] else None},
                 "journal_status": "installed_and_readback_verified", **stats}
        if bundle in SCIENTIFIC_NAMES:
            entry["scientific_name"] = SCIENTIFIC_NAMES[bundle]
        entries.append(entry)
        print(f"[{index:02d}/{len(candidates)}] {entry['species']}: {stats['patch_size'] / 1048576:.1f} MiB")
    manifest = {"format": "F4KP1", "version": args.version, "game": "Fisher Online",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(), "bundle_count": len(entries),
                "inventory_bundle_count": inventory["bundle_count"], "species": entries}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for name in ("Install-Fisher4K.ps1", "Restore-Fisher4K.ps1", "README.md", "RELEASE_NOTES.md"):
        shutil.copy2(Path.cwd() / name, output / name)
    print(json.dumps({"status": "built", "version": args.version, "bundles": len(entries),
                      "patch_bytes": sum(item["patch_size"] for item in entries), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
