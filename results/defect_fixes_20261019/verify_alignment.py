"""Verify native ELF and APK page alignment using the installed Android SDK."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import zipfile

folder = Path(__file__).resolve().parent
root = folder.parent.parent
sdk = Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk'
stage = sys.argv[1]
project = Path(sys.argv[2]) if len(sys.argv) > 2 else root / 'mobile/android'
apk = project / 'app/build/outputs/apk/debug/app-debug.apk'
library = folder / (stage + '_libkanglish_llama.so')
with zipfile.ZipFile(apk) as archive:
    library.write_bytes(archive.read('lib/arm64-v8a/libkanglish_llama.so'))
readelf = subprocess.check_output([
    str(sdk / 'ndk/27.2.12479018/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-readelf.exe'),
    '-lW', str(library)], text=True)
(folder / (stage + '_readelf.txt')).write_text(readelf, encoding='utf-8')
loads = [line.strip() for line in readelf.splitlines() if line.strip().startswith('LOAD ')]
assert loads and all(line.split()[-1] == '0x4000' for line in loads), loads
zipalign = subprocess.check_output([
    str(sdk / 'build-tools/35.0.0/zipalign.exe'), '-c', '-P', '16', '-v', '4', str(apk)], text=True)
(folder / (stage + '_zipalign.txt')).write_text(zipalign, encoding='utf-8')
record = {'load_segments': loads, 'zipalign_pass': True,
          'apk_sha256': hashlib.sha256(apk.read_bytes()).hexdigest()}
(folder / (stage + '_alignment.json')).write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record, indent=2))
