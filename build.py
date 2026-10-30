#!/usr/bin/env python3
"""Build the native all-user-app cleanup module; no phone mutation."""

import argparse
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
MODULE = ROOT / 'module'
NAME = 'sys_custom_clear_appfilter_list.xml'
TARGET = Path('system/my_product/etc/extension') / NAME
STOCK_HASH = '15e07bcaf96e0f63456e0b80dd74509fc53acd5362ceece12f0540210cc1018b'
VERSION = '0.3.0'


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
    return subprocess.run(['awk', '-f', str(MODULE / 'generate-policy.awk'), str(manifest), str(templates), str(stock)], check=True, capture_output=True).stdout


def validate_payload(stock, payload, apps, base):
    original = ET.fromstring(stock)
    patched = ET.fromstring(payload)
    if patched.findtext('version') != '2025112103':
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
    parser.add_argument('--packages', type=Path, default=ROOT / 'inputs/seed-apps.txt',
                        help='Build-time seed manifest; install and boot replace it with the device inventory.')
    args = parser.parse_args()
    companion_manifest = ET.parse(ROOT / 'manager/AndroidManifest.xml').getroot()
    android_name = '{http://schemas.android.com/apk/res/android}'
    if (companion_manifest.get('package') != 'io.github.dtingley11.letappslive'
            or companion_manifest.get(android_name + 'versionCode') != '3'
            or companion_manifest.get(android_name + 'versionName') != '0.2.0'):
        raise SystemExit('Companion identity/version does not match the module setup helper.')
    subprocess.run(['python3', str(ROOT / 'manager/build.py')], check=True)
    companion = MODULE / 'companion/LetAppsLive.apk'
    companion.parent.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'manager/dist/let-apps-live-manager-0.2.0-debug.apk', companion)
    stock_path = MODULE / 'stock' / NAME
    stock = stock_path.read_bytes()
    if sha256(stock).hexdigest() != STOCK_HASH:
        raise SystemExit('Stock file checksum does not match the reviewed firmware.')
    base = ET.parse(ROOT / 'inputs/native-base-policy.xml').getroot()
    if base.findtext('version') != '2125031040':
        raise SystemExit('Effective native policy changed; review its app rules.')
    apps = args.packages.read_text().splitlines()
    if apps != sorted(set(apps)) or not all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+', p) for p in apps):
        raise SystemExit('Invalid package manifest.')
    (MODULE / 'covered-packages.txt').write_text('\n'.join(apps) + ('\n' if apps else ''))
    (MODULE / 'policy-entries.tsv').write_text(templates_from_base(base))
    payload = generate(MODULE / 'covered-packages.txt', MODULE / 'policy-entries.tsv', stock_path)
    validate_payload(stock, payload, apps, base)
    target = MODULE / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    state_files = [TARGET.as_posix(), 'covered-packages.txt']
    (MODULE / 'state.sha256').write_text(''.join(sha256((MODULE / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in state_files))
    resources = ['stock/' + NAME, 'policy-entries.tsv', 'package-inventory.awk', 'generate-policy.awk',
                 'companion.sh', 'service.sh', 'companion/LetAppsLive.apk']
    (MODULE / 'resources.sha256').write_text(''.join(sha256((MODULE / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in resources))
    for script in MODULE.glob('*.sh'):
        subprocess.run(['sh', '-n', str(script)], check=True)
    allowed = {'module.prop', 'common.sh', 'customize.sh', 'post-fs-data.sh', 'action.sh',
               'companion.sh', 'service.sh', 'companion/LetAppsLive.apk', 'state.sha256',
               'resources.sha256', 'policy-entries.tsv', 'covered-packages.txt',
               'package-inventory.awk', 'generate-policy.awk', 'stock/' + NAME, TARGET.as_posix()}
    files = sorted(p for p in MODULE.rglob('*') if p.is_file())
    if {p.relative_to(MODULE).as_posix() for p in files} != allowed:
        raise SystemExit('Unexpected module files.')
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
    digest = sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest + '  ' + output.name + '\n')
    print(f'Validated {len(apps)} user-app entries, preserved native app rules, shell syntax, ZIP contents/CRC.\nBuilt: {output}\nSHA-256: {digest}')


if __name__ == '__main__':
    main()
