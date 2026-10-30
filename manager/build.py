#!/usr/bin/env python3
"""Build a small, dependency-free Android APK using the installed Android SDK."""

import argparse
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '0.2.1'


def run(args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=Path(os.environ.get('ANDROID_HOME', Path.home() / 'Android/Sdk')))
    parser.add_argument('--build-tools', default='36.0.0')
    args = parser.parse_args()
    tools = args.sdk / 'build-tools' / args.build_tools
    android = args.sdk / 'platforms/android-36/android.jar'
    for path in [android, *(tools / name for name in ['aapt2', 'd8', 'zipalign', 'apksigner'])]:
        if not path.is_file():
            raise SystemExit(f'Missing SDK tool or platform: {path}')
    for name in ['javac', 'jar', 'keytool']:
        if not shutil.which(name):
            raise SystemExit(f'Missing JDK command: {name}')
    build = ROOT / 'build'
    for name in ['generated', 'classes', 'dex']:
        if (build / name).exists():
            shutil.rmtree(build / name)
        (build / name).mkdir(parents=True, exist_ok=True)
    run([tools / 'aapt2', 'compile', '--dir', ROOT / 'res', '-o', build / 'resources.zip'])
    run([tools / 'aapt2', 'link', '-o', build / 'resources.apk', '-I', android,
         '--manifest', ROOT / 'AndroidManifest.xml', '--java', build / 'generated',
         build / 'resources.zip'])
    sources = sorted((ROOT / 'src').rglob('*.java')) + sorted((build / 'generated').rglob('*.java'))
    run(['javac', '--release', '17', '-encoding', 'UTF-8', '-classpath', android,
         '-d', build / 'classes', *sources])
    run(['jar', '--create', '--file', build / 'classes.jar', '-C', build / 'classes', '.'])
    run([tools / 'd8', '--release', '--min-api', '30', '--lib', android,
         '--output', build / 'dex', build / 'classes.jar'])
    unsigned = build / 'unsigned.apk'
    with zipfile.ZipFile(build / 'resources.apk') as resources, zipfile.ZipFile(unsigned, 'w') as archive:
        for name in sorted(resources.namelist()):
            info = zipfile.ZipInfo(name, (2026, 10, 29, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = resources.getinfo(name).compress_type
            archive.writestr(info, resources.read(name), compresslevel=9)
        for dex in sorted((build / 'dex').glob('*.dex')):
            info = zipfile.ZipInfo(dex.name, (2026, 10, 29, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, dex.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    run([tools / 'zipalign', '-f', '-p', '4', unsigned, build / 'aligned.apk'])
    signing = ROOT / '.signing'
    signing.mkdir(exist_ok=True)
    key = signing / 'debug.keystore'
    if not key.exists():
        run(['keytool', '-genkeypair', '-keystore', key, '-storepass', 'android',
             '-alias', 'androiddebugkey', '-keypass', 'android', '-keyalg', 'RSA',
             '-keysize', '2048', '-validity', '10000', '-dname', 'CN=Android Debug,O=Android,C=US'])
        key.chmod(0o600)
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    output = dist / f'let-apps-live-manager-{VERSION}-debug.apk'
    run([tools / 'apksigner', 'sign', '--ks', key, '--ks-pass', 'pass:android',
         '--key-pass', 'pass:android', '--ks-key-alias', 'androiddebugkey', '--out', output,
         build / 'aligned.apk'])
    run([tools / 'apksigner', 'verify', '--verbose', output])
    digest = sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.apk.sha256').write_text(digest + '  ' + output.name + '\n')
    print(f'Built: {output}\nBytes: {output.stat().st_size}\nSHA-256: {digest}')


if __name__ == '__main__':
    main()
