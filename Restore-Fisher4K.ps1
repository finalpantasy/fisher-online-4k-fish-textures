[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BackupPath,
    [string]$GamePath
)

$ErrorActionPreference = 'Stop'
if (Get-Process -Name 'theFisher' -ErrorAction SilentlyContinue) {
    throw 'Fisher Online is running. Close the game and run restore again.'
}

function Find-FisherOnline([string]$RequestedPath) {
    if ($RequestedPath) { return (Resolve-Path -LiteralPath $RequestedPath).Path }
    $journal = Join-Path $BackupPath 'installation.json'
    if (-not (Test-Path -LiteralPath $journal)) { throw 'installation.json is missing from the backup folder; provide -GamePath.' }
    $saved = (Get-Content -LiteralPath $journal -Raw | ConvertFrom-Json).backup
    return (Resolve-Path -LiteralPath (Split-Path -Parent (Split-Path -Parent $saved))).Path
}

$gameRoot = Find-FisherOnline $GamePath
$allowedRoot = [IO.Path]::GetFullPath((Join-Path $gameRoot 'Mod Backups'))
$resolvedBackup = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $BackupPath).Path)
if (-not $resolvedBackup.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'BackupPath must be inside this Fisher Online installation''s Mod Backups folder.'
}
$bundleRoot = Join-Path $gameRoot 'theFisher_Data\StreamingAssets\aa\StandaloneWindows64'
$journal = Get-Content -LiteralPath (Join-Path $resolvedBackup 'installation.json') -Raw | ConvertFrom-Json
foreach ($bundle in $journal.bundles) {
    $source = Join-Path $resolvedBackup $bundle
    $destination = Join-Path $bundleRoot $bundle
    if (-not (Test-Path -LiteralPath $source)) { throw "Backup file missing: $bundle" }
    $temporary = "$destination.restore.tmp"
    Copy-Item -LiteralPath $source -Destination $temporary
    [System.IO.File]::Replace($temporary, $destination, $null)
    Write-Host "Restored: $bundle"
}
Write-Host 'Restore completed.'
