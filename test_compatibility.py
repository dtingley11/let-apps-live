from hashlib import sha256
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
COMPILER = 'io.github.dtingley11.letappslive.PolicyCompiler'


def policy(kind, version, rules=''):
    prefix = 'custom_' if kind == 'custom' else ''
    return (f'<filter-conf><filter-name>sys_{prefix}clear_appfilter_list</filter-name>'
            f'<version>{version}</version><isOpen>1</isOpen>{rules}</filter-conf>')


class PolicyCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = tempfile.TemporaryDirectory()
        subprocess.run(['javac', '-d', cls.classes.name, str(ROOT / 'manager/src' /
                        Path(COMPILER.replace('.', '/') + '.java'))], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.classes.cleanup()

    def compile(self, root, *, custom=None, base=None, remote_base='No result found.',
                remote_custom='No result found.', visible=None, apps='com.example.chat\n'):
        custom = custom or policy('custom', 123, '<p_wl pkg="com.example.chat" use_kill="false" custom="retained"/>')
        base = base or policy('', 200, '<p_wl pkg="com.example.chat" use_kill="false" base="not-custom"/>')
        values = [custom, base, remote_base, remote_custom, visible or custom, apps]
        paths = [root / name for name in ['original.xml', 'base.xml', 'remote-base.txt',
                                         'remote-custom.txt', 'visible.xml', 'apps.txt']]
        for path, value in zip(paths, values):
            path.write_text(value)
        return subprocess.run(['java', '-cp', self.classes.name, COMPILER, *map(str, paths),
                               str(root / 'prepared')], capture_output=True, text=True)

    def generate(self, root):
        prepared = root / 'prepared'
        result = subprocess.run(['awk', '-v', 'policy_version=' + (prepared / 'policy-version.txt').read_text().strip(),
                                 '-f', str(ROOT / 'module/generate-policy.awk'), str(root / 'apps.txt'),
                                 str(prepared / 'policy-entries.tsv'), str(prepared / 'custom-policy.xml')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return ET.fromstring(result.stdout)

    def test_device_versions_and_existing_custom_fields_are_preserved(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            custom = policy('custom', 77, '<p_wl pkg="com.example.chat" custom="keep"/>'
                            '<other field="unchanged"/><p_crm pkg="com.example.untouched" use_kill="false"/>')
            result = self.compile(root, custom=custom)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = self.generate(root)
            self.assertEqual(output.findtext('version'), '78')
            rules = output.findall('p_wl')
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0].attrib, {'pkg': 'com.example.chat', 'custom': 'keep', 'use_kill': 'true'})
            self.assertEqual(output.find('other').attrib, {'field': 'unchanged'})
            self.assertEqual(output.find('p_crm').get('use_kill'), 'false')
            self.assertEqual((root / 'prepared/original-custom.xml').read_text(), custom)

    def test_newer_downloaded_policies_and_conditional_precedence(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            downloaded = policy('', 900, '<p_cond_wl pkg="com.example.chat" use_kill="false" keep="conditional"/>'
                                '<p_wl pkg="com.example.chat" use_kill="false" keep="ordinary"/>')
            custom = policy('custom', 600, '<device_setting value="new"/>')
            visible = policy('custom', 999)
            result = self.compile(root, remote_base='Row: 0 xml=' + downloaded,
                                  remote_custom='Row: 0 xml=' + custom, visible=visible)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = self.generate(root)
            self.assertEqual(output.findtext('version'), '1000')
            self.assertEqual(output.find('device_setting').get('value'), 'new')
            self.assertEqual(output.find('p_cond_wl').attrib,
                             {'pkg': 'com.example.chat', 'use_kill': 'true', 'keep': 'conditional'})
            self.assertIsNone(output.find('p_wl'))
            self.assertEqual((root / 'prepared/source-versions.txt').read_text(), 'base=900\ncustom=600\n')

    def test_lower_downloaded_policy_does_not_replace_native(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            result = self.compile(root, remote_custom=policy('custom', 1, '<old/>'))
            self.assertEqual(result.returncode, 0, result.stderr)
            output = self.generate(root)
            self.assertIsNone(output.find('old'))
            self.assertEqual(output.find('p_wl').get('custom'), 'retained')
            self.assertEqual(output.find('p_wl').get('use_kill'), 'true')

    def test_unsupported_inputs_are_rejected(self):
        cases = [
            {'remote_base': 'Error while accessing provider'},
            {'custom': policy('custom', 2147483647)},
            {'custom': '<!DOCTYPE filter-conf [<!ENTITY x "value">]>' + policy('custom', 123)},
            {'custom': policy('custom', 123, '<p_wl pkg="com.example.chat"><nested/></p_wl>')},
            {'base': policy('', 1, '<p_wl pkg="com.example.chat"/>')},
            {'apps': 'com.example.z\ncom.example.a\n'},
            {'apps': 'com.example.chat\ncom.example.chat\n'},
            {'custom': policy('custom', 123).replace('<isOpen>1', '<isOpen>0')},
        ]
        for values in cases:
            with self.subTest(values=values), tempfile.TemporaryDirectory() as work:
                result = self.compile(Path(work), **values)
                self.assertNotEqual(result.returncode, 0)


class PlatformCompatibilityTests(unittest.TestCase):
    def shell(self, root, body, **props):
        script = '''
            MODDIR=$1
            . "$2"
            getprop() {
                case "$1" in
                    ro.product.brand|ro.product.manufacturer) printf '%s' "$BRAND" ;;
                    ro.oplus.image.system_ext.area) printf '%s' "$AREA" ;;
                    persist.sys.oplus.region) printf '%s' "$REGION" ;;
                    ro.oplus.regionmark) printf '%s' "$REGIONMARK" ;;
                    ro.build.version.sdk) printf '%s' "$SDK" ;;
                    ro.build.display.id) printf '%s' "$BUILD" ;;
                esac
            }
            athena_mount_check() { return 0; }
        ''' + body + '\nprintf "%s\\n" "$ATHENA_ERROR"\nexit "$result"\n'
        env = dict(os.environ, BRAND='OnePlus', AREA='domestic', REGION='', REGIONMARK='', SDK='36', BUILD='different_device_build')
        env.update(props)
        return subprocess.run(['sh', '-c', script, 'test', str(root), str(ROOT / 'module/common.sh')],
                              env=env, capture_output=True, text=True)

    def test_other_oneplus_china_builds_are_accepted(self):
        for props in [{'SDK': '30'}, {'BUILD': 'another_firmware'}, {'AREA': '', 'REGION': 'CN'},
                      {'AREA': '', 'REGIONMARK': 'CN'}]:
            with self.subTest(props=props), tempfile.TemporaryDirectory() as work:
                root = Path(work)
                (root / 'resource').write_text('fixture')
                (root / 'resources.sha256').write_text(sha256(b'fixture').hexdigest() + '  resource\n')
                result = self.shell(root, 'athena_check_platform; result=$?\n', **props)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_incompatible_platforms_are_rejected(self):
        for props in [{'BRAND': 'Google'}, {'AREA': 'export', 'REGION': 'US'}, {'SDK': '29'}]:
            with self.subTest(props=props), tempfile.TemporaryDirectory() as work:
                result = self.shell(Path(work), 'athena_check_platform; result=$?\n', **props)
                self.assertNotEqual(result.returncode, 0)

    def test_legacy_provider_is_tried_after_an_empty_failed_query(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            body = '''
                timeout() {
                    case "$*" in
                        *com.oplus.romupdate.provider.db*) return 0 ;;
                        *com.nearme.romupdate.provider.db*) printf 'No result found.\\n' ;;
                        *) return 1 ;;
                    esac
                }
                athena_query_updates "$MODDIR"; result=$?
            '''
            result = self.shell(root, body)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / 'remote-base.txt').read_text(), 'No result found.\n')
            self.assertEqual((root / 'remote-custom.txt').read_text(), 'No result found.\n')

    def test_changed_firmware_apk_or_native_policy_requires_reinstall(self):
        for changed in [None, 'BUILD', 'apk', 'native']:
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as work:
                root = Path(work)
                device = root / 'device'
                device.mkdir()
                files = {'resource': 'resource', 'apk': 'athena', 'native': 'native',
                         'device/build-id.txt': 'different_device_build',
                         'device/original-custom.xml': 'native', 'covered-packages.txt': 'com.example.app\n'}
                files['device/athena-apk.txt'] = str(root / 'apk')
                files['device/athena-apk.sha256'] = sha256(b'athena').hexdigest()
                for name, value in files.items():
                    (root / name).write_text(value)
                for manifest, names in [('resources.sha256', ['resource']),
                                        ('state.sha256', ['covered-packages.txt']),
                                        ('device-state.sha256', [str(p.relative_to(root)) for p in device.iterdir()])]:
                    (root / manifest).write_text(''.join(sha256((root / n).read_bytes()).hexdigest() + '  ' + n + '\n' for n in names))
                if changed in {'apk', 'native'}:
                    (root / changed).write_text('changed')
                body = 'athena_load_target() { ATHENA_TARGET="$MODDIR/native"; }\nathena_check boot; result=$?\n'
                result = self.shell(root, body, **({'BUILD': 'updated'} if changed == 'BUILD' else {}))
                self.assertEqual(result.returncode == 0, changed is None, result.stdout + result.stderr)

    def test_upgrade_recovers_only_verified_same_firmware_original(self):
        for legacy in [False, True]:
            for changed in [None, 'BUILD', 'overlay', 'original']:
                with self.subTest(legacy=legacy, changed=changed), tempfile.TemporaryDirectory() as work:
                    root = Path(work)
                    previous = root / 'previous'
                    previous.mkdir()
                    (previous / 'overlay').write_text('generated')
                    if legacy:
                        original = previous / 'stock/sys_custom_clear_appfilter_list.xml'
                        resources = ['common.sh', str(original.relative_to(previous))]
                        (previous / 'common.sh').write_text("ATHENA_BUILD='different_device_build'\n")
                    else:
                        original = previous / 'device/original-custom.xml'
                        resources = ['common.sh']
                        (previous / 'common.sh').write_text('fixture')
                        original.parent.mkdir()
                        (previous / 'device/build-id.txt').write_text('different_device_build')
                    original.parent.mkdir(exist_ok=True)
                    original.write_text('original')
                    manifests = [('resources.sha256', resources), ('state.sha256', ['overlay'])]
                    if not legacy:
                        manifests.append(('device-state.sha256', ['device/original-custom.xml', 'device/build-id.txt']))
                    for name, entries in manifests:
                        (previous / name).write_text(''.join(sha256((previous / e).read_bytes()).hexdigest()
                                                           + '  ' + e + '\n' for e in entries))
                    if changed == 'overlay':
                        (previous / 'overlay').write_text('tampered')
                    if changed == 'original':
                        original.write_text('tampered')
                    body = ('ATHENA_MODULE="$MODDIR/previous"\n'
                            'athena_previous_original overlay ' + sha256(b'generated').hexdigest() + '; result=$?\n')
                    result = self.shell(root, body, **({'BUILD': 'updated'} if changed == 'BUILD' else {}))
                    self.assertEqual(result.returncode == 0, changed is None, result.stdout + result.stderr)
                    if changed is None:
                        self.assertIn(str(original), result.stdout)


if __name__ == '__main__':
    unittest.main()
