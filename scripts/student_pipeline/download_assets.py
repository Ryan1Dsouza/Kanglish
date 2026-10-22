"""Download pinned public IndicXlit artifacts; no hosted model inference or keys."""
from pathlib import Path
import argparse
import urllib.request
import zipfile
from .contract import sha,write_json

ARCHIVE_URL='https://github.com/AI4Bharat/IndicXlit/releases/download/v1.0/indicxlit-indic-en-v1.0.zip'
ARCHIVE_SHA='420d23a13cfa953edfb47644bc805de06e97134f25e6d182303a29f55b5a3322'
CHECKPOINT_SHA='45ffecef88d990ae12f915939b91267a3fc8f69f26331baa59f7932005976f28'
WHEEL_URL='https://files.pythonhosted.org/packages/04/34/9649b4fbc53fe7b038b70666b031f586d81f7b085e610cb9c3873cb5bd8e/ai4bharat_transliteration-1.1.3-py3-none-any.whl'

def download(url,path):
    if path.exists():return
    pending=path.with_suffix(path.suffix+'.part')
    with urllib.request.urlopen(url,timeout=60) as source,pending.open('wb') as out:
        while block:=source.read(1024*1024):out.write(block)
    pending.replace(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=Path('models/indicxlit_v1'))
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    archive=args.out/'indicxlit-indic-en-v1.0.zip';download(ARCHIVE_URL,archive)
    if sha(archive)!=ARCHIVE_SHA:raise ValueError('IndicXlit archive differs from the pinned release')
    checkpoint=args.out/'transformer/indicxlit.pt'
    if not checkpoint.exists():
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not (args.out/name).resolve().is_relative_to(args.out.resolve()):raise ValueError('Unsafe archive path')
            z.extractall(args.out)
    if sha(checkpoint)!=CHECKPOINT_SHA:raise ValueError('Checkpoint differs from pinned release')
    wheel=args.out/'ai4bharat_transliteration-1.1.3-py3-none-any.whl';download(WHEEL_URL,wheel)
    write_json(args.out/'download_manifest.json',{'model':'AI4Bharat/IndicXlit indic-en v1.0','archive_url':ARCHIVE_URL,
        'archive_sha256':sha(archive),'checkpoint_sha256':sha(checkpoint),'package_url':WHEEL_URL,'package_sha256':sha(wheel),
        'use':'local pretrained Romanization only; no student training','hosted_model_api_calls':0})
    print('Pinned IndicXlit artifacts are ready.')

if __name__=='__main__':main()
