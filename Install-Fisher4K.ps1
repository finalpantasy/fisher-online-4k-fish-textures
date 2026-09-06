[CmdletBinding()]
param(
    [string]$GamePath,
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Find-FisherOnline([string]$RequestedPath) {
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($RequestedPath) { $candidates.Add($RequestedPath) }
    $steamRoots = [System.Collections.Generic.List[string]]::new()
    try {
        $steam = (Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam').SteamPath
        if ($steam) { $steamRoots.Add($steam) }
    } catch {}
    foreach ($default in @(
        "${env:ProgramFiles(x86)}\Steam",
        "$env:ProgramFiles\Steam",
        'C:\Steam', 'D:\Steam', 'E:\Steam', 'F:\Steam', 'G:\Steam'
    )) {
        if ($default -and (Test-Path -LiteralPath $default)) { $steamRoots.Add($default) }
    }
    foreach ($root in @($steamRoots | Select-Object -Unique)) {
        $candidates.Add((Join-Path $root 'steamapps\common\theFisher Online'))
        $vdf = Join-Path $root 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            foreach ($match in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw), '"path"\s+"([^"]+)"')) {
                $library = $match.Groups[1].Value -replace '\\\\', '\'
                $candidates.Add((Join-Path $library 'steamapps\common\theFisher Online'))
            }
        }
    }
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        $bundleRoot = Join-Path $candidate 'theFisher_Data\StreamingAssets\aa\StandaloneWindows64'
        if (Test-Path -LiteralPath $bundleRoot) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    throw 'Fisher Online was not found. Re-run with -GamePath "X:\Steam\steamapps\common\theFisher Online".'
}

function Read-Exact([System.IO.Stream]$Stream, [int]$Count) {
    $buffer = New-Object byte[] $Count
    $offset = 0
    while ($offset -lt $Count) {
        $read = $Stream.Read($buffer, $offset, $Count - $offset)
        if ($read -le 0) { throw "Unexpected end of compressed patch data ($offset of $Count bytes)." }
        $offset += $read
    }
    return $buffer
}

function Apply-F4KPatch([string]$Source, [string]$Patch, [string]$Output, $Entry) {
    Copy-Item -LiteralPath $Source -Destination $Output
    $patchStream = [System.IO.File]::OpenRead($Patch)
    $reader = [System.IO.BinaryReader]::new($patchStream)
    $outputStream = $null
    try {
        $magic = [Text.Encoding]::ASCII.GetString($reader.ReadBytes(6))
        if ($magic -ne "F4KP1`0") { throw "Unsupported patch format in $Patch" }
        $sourceSize = $reader.ReadUInt64()
        $targetSize = $reader.ReadUInt64()
        $sourceHash = ([BitConverter]::ToString($reader.ReadBytes(32))).Replace('-', '').ToLowerInvariant()
        $targetHash = ([BitConverter]::ToString($reader.ReadBytes(32))).Replace('-', '').ToLowerInvariant()
        $blockSize = $reader.ReadUInt32()
        $blockCount = $reader.ReadUInt32()
        if ($sourceSize -ne (Get-Item -LiteralPath $Source).Length -or $sourceHash -ne $Entry.source_sha256) {
            throw "Patch source metadata mismatch for $($Entry.bundle)"
        }
        if ($targetSize -ne $Entry.target_size -or $targetHash -ne $Entry.target_sha256) {
            throw "Patch target metadata mismatch for $($Entry.bundle)"
        }
        $outputStream = [System.IO.File]::Open($Output, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $outputStream.SetLength([int64]$targetSize)
        for ($index = 0; $index -lt $blockCount; $index++) {
            $offset = $reader.ReadUInt64()
            $rawLength = $reader.ReadUInt32()
            $compressedLength = $reader.ReadUInt32()
            if ($rawLength -gt $blockSize -or ($offset + $rawLength) -gt $targetSize) {
                throw "Invalid patch block $index for $($Entry.bundle)"
            }
            $compressed = $reader.ReadBytes([int]$compressedLength)
            if ($compressed.Length -ne $compressedLength) { throw "Truncated patch block $index" }
            $memory = [System.IO.MemoryStream]::new($compressed, $false)
            $gzip = [System.IO.Compression.GZipStream]::new($memory, [System.IO.Compression.CompressionMode]::Decompress)
            try { $raw = Read-Exact $gzip ([int]$rawLength) } finally { $gzip.Dispose(); $memory.Dispose() }
            $outputStream.Position = [int64]$offset
            $outputStream.Write($raw, 0, $raw.Length)
        }
    } finally {
        if ($outputStream) { $outputStream.Dispose() }
        $reader.Dispose()
        $patchStream.Dispose()
    }
    if ((Get-Sha256 $Output) -ne $Entry.target_sha256) {
        throw "Patched output hash mismatch for $($Entry.bundle)"
    }
}

if (Get-Process -Name 'theFisher' -ErrorAction SilentlyContinue) {
    throw 'Fisher Online is running. Close the game and run the installer again.'
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifestPath = Join-Path $root 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'manifest.json is missing beside the installer.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$gameRoot = Find-FisherOnline $GamePath
$bundleRoot = Join-Path $gameRoot 'theFisher_Data\StreamingAssets\aa\StandaloneWindows64'

foreach ($entry in $manifest.species) {
    $destination = Join-Path $bundleRoot $entry.bundle
    $patch = Join-Path $root $entry.patch
    if (-not (Test-Path -LiteralPath $destination)) { throw "Missing game bundle: $($entry.bundle)" }
    if (-not (Test-Path -LiteralPath $patch)) { throw "Missing patch: $($entry.patch)" }
    if ((Get-Sha256 $patch) -ne $entry.patch_sha256) { throw "Patch checksum failed: $($entry.patch)" }
    $current = Get-Sha256 $destination
    if ($current -eq $entry.target_sha256) { continue }
    if ($current -ne $entry.source_sha256) {
        throw "Unsupported game/mod state for $($entry.bundle). Use Steam Verify Integrity, or restore an earlier texture backup, then retry."
    }
}

if ($VerifyOnly) {
    Write-Host "All $($manifest.bundle_count) targets and patches passed preflight for release $($manifest.version)."
    exit 0
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $gameRoot "Mod Backups\FisherOnline-4K-Public-before-$stamp"
New-Item -ItemType Directory -Path $backupRoot | Out-Null
$installed = [System.Collections.Generic.List[object]]::new()
try {
    foreach ($entry in $manifest.species) {
        $destination = Join-Path $bundleRoot $entry.bundle
        if ((Get-Sha256 $destination) -eq $entry.target_sha256) { continue }
        $backup = Join-Path $backupRoot $entry.bundle
        Copy-Item -LiteralPath $destination -Destination $backup
        if ((Get-Sha256 $backup) -ne $entry.source_sha256) { throw "Backup verification failed for $($entry.bundle)" }
    }
    foreach ($entry in $manifest.species) {
        $destination = Join-Path $bundleRoot $entry.bundle
        if ((Get-Sha256 $destination) -eq $entry.target_sha256) { continue }
        if (Get-Process -Name 'theFisher' -ErrorAction SilentlyContinue) { throw 'Fisher Online started during installation.' }
        $temporary = "$destination.f4k-$stamp.tmp"
        Apply-F4KPatch $destination (Join-Path $root $entry.patch) $temporary $entry
        [System.IO.File]::Replace($temporary, $destination, $null)
        if ((Get-Sha256 $destination) -ne $entry.target_sha256) { throw "Installed hash mismatch for $($entry.bundle)" }
        $installed.Add($entry)
        Write-Host "Installed: $($entry.species)"
    }
} catch {
    for ($index = $installed.Count - 1; $index -ge 0; $index--) {
        $entry = $installed[$index]
        Copy-Item -LiteralPath (Join-Path $backupRoot $entry.bundle) -Destination (Join-Path $bundleRoot $entry.bundle) -Force
    }
    throw
}

$journal = @{
    status = 'installed_and_hash_verified'
    version = $manifest.version
    installed_at = (Get-Date).ToString('o')
    backup = $backupRoot
    bundles = @($installed | ForEach-Object { $_.bundle })
}
$journal | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $backupRoot 'installation.json') -Encoding UTF8
Write-Host "Installed Fisher Online 4K Fish Textures $($manifest.version)."
Write-Host "Rollback backup: $backupRoot"
