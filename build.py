#!/usr/bin/env python3
"""Build the native all-user-app cleanup module; no phone mutation."""

import argparse
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
MODULE = ROOT / 'module'
VERSION = '0.4.1'


def semantic(node):
    return (node.tag, tuple(sorted(node.attrib.items())), (node.text or '').strip(), tuple(semantic(c) for c in node))


def templates_from_base(base):
    # Athena's conditional entries override ordinary/CRM entries regardless of
    # ordering. Retain each entry's native tag and attributes, not just use_kill.
    normal, conditional = {}, {}
    for node in base:
        if node.tag in {'p_wl', 'p_crm'}:
            normal[node.attrib['pkg']] = deepcopy(node)
        elif node.tag == 'p_cond_wl':
            conditional[node.attrib['pkg']] = deepcopy(node)
    normal.update(conditional)
    rows = []
    for name, node in sorted(normal.items()):
        node.set('use_kill', 'true')
        node.tail = None
        rows.append(name + '\t' + ET.tostring(node, encoding='unicode'))
    return '\n'.join(rows) + '\n'


def generate(manifest, templates, stock):
    version = str(int(ET.parse(stock).getroot().findtext('version')) + 1)
    return subprocess.run(['awk', '-v', 'policy_version=' + version, '-f', str(MODULE / 'generate-policy.awk'), str(manifest), str(templates), str(stock)], check=True, capture_output=True).stdout


def validate_payload(stock, payload, apps, base):
    original = ET.fromstring(stock)
    patched = ET.fromstring(payload)
    if int(patched.findtext('version')) != int(original.findtext('version')) + 1:
        raise ValueError('Unexpected generated policy version.')
    if len(patched) != len(original) + len(apps):
        raise ValueError('Unexpected number of policy entries.')
    restored = deepcopy(patched)
    for child in list(restored)[len(original):]:
        restored.remove(child)
    restored.find('version').text = original.findtext('version')
    if semantic(restored) != semantic(original):
        raise ValueError('Original custom policy changed.')
    expected = dict(line.split('\t', 1) for line in templates_from_base(base).splitlines())
    for app, node in zip(apps, list(patched)[len(original):]):
        if node.get('pkg') != app or node.get('use_kill') != 'true':
            raise ValueError('App coverage mismatch.')
        wanted = ET.fromstring(expected[app]) if app in expected else ET.Element('p_cond_wl', {'pkg': app, 'use_kill': 'true'})
        if semantic(node) != semantic(wanted):
            raise ValueError('An existing per-app policy was changed beyond use_kill.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    companion_manifest = ET.parse(ROOT / 'manager/AndroidManifest.xml').getroot()
    android_name = '{http://schemas.android.com/apk/res/android}'
    package = companion_manifest.get('package')
    code = companion_manifest.get(android_name + 'versionCode')
    version = companion_manifest.get(android_name + 'versionName')
    declared_code = re.search(r'^LAL_VERSION_CODE=([0-9]+)$', (MODULE / 'companion.sh').read_text(), re.M)
    if package != 'io.github.dtingley11.letappslive' or not declared_code or declared_code.group(1) != code:
        raise SystemExit('Companion identity/version does not match the setup helper.')
    subprocess.run(['python3', str(ROOT / 'manager/build.py')], check=True)
    companion = MODULE / 'companion/LetAppsLive.apk'
    companion.parent.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / ('manager/dist/let-apps-live-manager-' + version + '-debug.apk'), companion)
    allowed = {'module.prop', 'common.sh', 'customize.sh', 'post-fs-data.sh', 'action.sh',
               'companion.sh', 'service.sh', 'companion/LetAppsLive.apk', 'resources.sha256',
               'package-inventory.awk', 'generate-policy.awk'}
    resources = sorted(allowed - {'module.prop', 'resources.sha256', 'customize.sh'})
    (MODULE / 'resources.sha256').write_text(''.join(sha256((MODULE / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in resources))
    for script in MODULE.glob('*.sh'):
        subprocess.run(['sh', '-n', str(script)], check=True)
    files = sorted(MODULE / name for name in allowed)
    if not all(path.is_file() for path in files):
        raise SystemExit('A required module file is missing.')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    output = dist / ('let-apps-live-' + VERSION + '.zip')
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(MODULE).as_posix(), (2026, 10, 29, 0, 0, 0))
            info.create_system = 3
            mode = 0o755 if path.name in {'post-fs-data.sh', 'action.sh', 'service.sh'} else 0o644
            info.external_attr = (0o100000 | mode) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() or set(archive.namelist()) != allowed:
            raise SystemExit('ZIP validation failed.')
    with tempfile.TemporaryDirectory() as installed:
        with zipfile.ZipFile(output) as archive:
            archive.extractall(installed)
        (Path(installed) / 'customize.sh').unlink()
        subprocess.run(['sha256sum', '-c', 'resources.sha256'], cwd=installed, check=True, capture_output=True)
    digest = sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest + '  ' + output.name + '\n')
    print(f'Built: {output}\nSHA-256: {digest}')


if __name__ == '__main__':
    main()
