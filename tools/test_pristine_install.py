"""Black-box multipart install and restore test from independently found originals."""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, tempfile, zipfile
from pathlib import Path
from build_release import SPECIES, load_journal_records, load_retained_pristine_sources
from verify_release import sha256
PS=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
def run(script, *args, env=None):
    """Capture child output so a long public install cannot block our runner pipe."""
    completed = subprocess.run(
        [PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *map(str, args)],
        check=False, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1800,
    )
    if completed.returncode:
        raise RuntimeError(f"{script.name} failed ({completed.returncode}):\n{completed.stdout}")
    return completed.stdout
def main():
 p=argparse.ArgumentParser();p.add_argument('--dist',type=Path,required=True);p.add_argument('--artifacts',type=Path,required=True);p.add_argument('--version');a=p.parse_args();dist=a.dist.resolve()
 asset_files=list(dist.glob('*-assets.json'))
 if a.version:
  asset_files=[path for path in asset_files if f'-v{a.version}-assets.json' in path.name]
 if not asset_files: raise FileNotFoundError('No matching release assets manifest')
 asset_file=max(asset_files,key=lambda path:path.stat().st_mtime_ns)
 assets=json.loads(asset_file.read_text())['assets']
 with tempfile.TemporaryDirectory(dir=dist) as td:
  td=Path(td); parts=[]
  for asset in assets:
   d=td/asset['asset'].removesuffix('.zip');d.mkdir();zipfile.ZipFile(dist/asset['asset']).extractall(d);parts.append(d)
  manifests=[json.loads((d/'manifest.json').read_text()) for d in parts]; entries=[e for m in manifests for e in m['species']]
  records=load_journal_records(a.artifacts); originals=load_retained_pristine_sources(a.artifacts,set(SPECIES),records)
  game=td/'theFisher Online'; root=game/'theFisher_Data/StreamingAssets/aa/StandaloneWindows64';root.mkdir(parents=True)
  for e in entries:
   source=originals[e['bundle']]['path'];shutil.copy2(source,root/e['bundle'])
   if sha256(root/e['bundle'])!=originals[e['bundle']]['sha256']:raise ValueError('independent pristine mismatch')
  for d in parts: run(d/'Install-Fisher4K.ps1','-GamePath',game)
  for e in entries:
   if sha256(root/e['bundle'])!=e['target_sha256']:raise ValueError(f'install mismatch: {e["bundle"]}')
  journals=sorted((game/'Mod Backups').glob('FisherOnline-4K-Public-before-*/installation.json'))
  # Windows PowerShell's -File boundary does not preserve a Python argv slice
  # as one string[] parameter. Restore each disjoint part journal explicitly.
  for journal in journals:
   run(parts[0]/'Restore-Fisher4K.ps1','-GamePath',game,'-BackupPath',journal.parent)
  for e in entries:
   if sha256(root/e['bundle'])!=originals[e['bundle']]['sha256']:raise ValueError(f'restore mismatch: {e["bundle"]}')
 print(json.dumps({'status':'multipart_pristine_install_restore_verified','bundles':len(entries)}))
if __name__=='__main__':main()
