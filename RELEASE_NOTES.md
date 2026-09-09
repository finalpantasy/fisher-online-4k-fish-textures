## Fisher Online 4K Fish Textures v0.1.4

This public preview expands from 96 to 133 currently verified bundle patches.

- 133 version-locked patches selected from the authoritative 310-bundle live inventory
- adds the current verified run through Norwegian Saithe, including Atka
  Mackerel, Chinese Sturgeon, Mud Carp, Wuchang Bream, Blue Tilapia, three koi
  families, Leaping Mullet, Lake Char, Rhone Trout, gobies, dace, salmon,
  crayfish, shrimp, catfish, bass, and related rebuilt packages
- Atka Mackerel and Norwegian Saithe use explicit dual-eye UV landmark checks;
  Norwegian Saithe also audits its separately skinned body and fin meshes
- every newly built package is checked after Unity serialization for 4096x4096
  payloads, 13 mip levels, original-mesh appearance, and panel seams
- every selected current live SHA-256 has a unique `installed_and_readback_verified`
  lineage back to an earliest recorded pristine rollback source
- Chum Salmon and the original Yellowfin Tuna package remain temporarily
  omitted because their latest local repairs do not yet have a complete
  publishable journal chain; Baltic and Silver Salmon are included
- Brook Charr (`Salvelinus fontinalis`) is correctly named for
  `fishs_assets_fishingame_74_palia.bundle`; it is not Arctic char
- self-contained deterministic archive parts, each below GitHub's 2 GiB
  release-asset limit; install every part once
- dependency-free Windows PowerShell installer with SHA-256 preflight, dated
  backups, staged replacement, and automatic rollback
- no original Fisher Online bundles included in the download

Read `README.md` inside each archive before installing. Fisher Online must be
closed, and Steam Verify Integrity should be run first so source bundle hashes
match this release.
