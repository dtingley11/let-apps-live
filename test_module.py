from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import build


class ModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        cls.templates = Path(cls.work.name) / 'templates.tsv'
        base = ET.parse(build.ROOT / 'inputs/native-base-policy.xml').getroot()
        cls.templates.write_text(build.templates_from_base(base))
        cls.stock = build.ROOT / 'inputs/reference-custom-policy.xml'

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def inventory(self, packages, users='<package-restrictions></package-restrictions>'):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'packages.xml').write_text(packages)
            (root / 'users.xml').write_text(users)
            return subprocess.run(
                ['awk', '-f', str(build.MODULE / 'package-inventory.awk'), str(root / 'users.xml'), str(root / 'packages.xml')],
                capture_output=True, text=True,
            )

    def test_system_flag_excludes_factory_and_updated_system_apps(self):
        result = self.inventory('''<packages>
          <package name="com.example.user" publicFlags="538459716" />
          <package name="com.example.factory" publicFlags="1" />
          <package name="com.example.updated" codePath="/data/app/update" publicFlags="129" />
          <package name="com.google.android.gms" publicFlags="-1605714235" />
          <package name="com.example.negative.user" publicFlags="-2147483648" />
        </packages>''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.splitlines()), {'com.example.user', 'com.example.negative.user'})

    def test_uninstalled_for_main_user_is_excluded(self):
        result = self.inventory(
            '<packages><package name="com.example.old" publicFlags="0" /><package name="com.example.current" publicFlags="0" /></packages>',
            '<package-restrictions><pkg name="com.example.old" inst="false" /></package-restrictions>',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['com.example.current'])

    def test_older_flags_attribute_is_supported(self):
        result = self.inventory('<packages><package name="com.example.user" flags="0" />'
                                '<package name="com.example.system" flags="129" /></packages>')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['com.example.user'])

    def test_framework_resource_package_names_are_not_user_apps(self):
        result = self.inventory(
            '<packages><package name="android" publicFlags="810073609" /><package name="oplus" publicFlags="805846529" /><package name="com.example.user" publicFlags="0" /></packages>',
            '<package-restrictions><pkg name="android" /><pkg name="oplus" /><pkg name="com.example.user" /></package-restrictions>',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['com.example.user'])

    def test_new_install_and_uninstall_rebuild_the_list(self):
        def database(names):
            return '<packages>' + ''.join(f'<package name="{p}" publicFlags="0" />' for p in names) + '</packages>'
        before = self.inventory(database(['com.example.first']))
        after = self.inventory(database(['com.example.first', 'com.example.new']))
        removed = self.inventory(database(['com.example.new']))
        self.assertEqual(set(before.stdout.splitlines()), {'com.example.first'})
        self.assertEqual(set(after.stdout.splitlines()), {'com.example.first', 'com.example.new'})
        self.assertEqual(set(removed.stdout.splitlines()), {'com.example.new'})

    def test_incomplete_or_unknown_database_is_rejected_without_partial_list(self):
        for data in [
            '<packages><package name="com.example.ok" publicFlags="0" />',
            '<packages><package name="com.example.ok" publicFlags="0" /><package name="com.example.unknown" /></packages>',
            '<packages><package name="com.example.bad&amp;name" publicFlags="0" /></packages>',
        ]:
            with self.subTest(data=data):
                result = self.inventory(data)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')

    def test_generated_policy_preserves_native_fields_and_custom_stock(self):
        base = ET.parse(build.ROOT / 'inputs/native-base-policy.xml').getroot()
        stock_path = self.stock
        # Exercise known policy shapes without using a personal app inventory.
        apps = ['com.heytap.health', 'com.taobao.taobao']
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / 'apps.txt'
            manifest.write_text('\n'.join(apps) + '\n')
            payload = build.generate(manifest, self.templates, stock_path)
        build.validate_payload(stock_path.read_bytes(), payload, apps, base)
        nodes = {e.get('pkg'): e for e in ET.fromstring(payload) if e.get('pkg') in apps}
        self.assertEqual(nodes['com.heytap.health'].get('proc_keep'), 'com.heytap.health:transport')
        self.assertEqual(nodes['com.heytap.health'].get('remove_task_filter'), 'com.heytap.health:transport')
        self.assertEqual(nodes['com.taobao.taobao'].tag, 'p_crm')
        self.assertEqual(nodes['com.taobao.taobao'].get('source'), 'pangu')
        self.assertEqual(nodes['com.taobao.taobao'].get('remove_task_filter'), '$')
        self.assertNotIn('com.google.android.gms', nodes)
        self.assertNotIn('com.android.settings', nodes)

    def test_new_app_gets_plain_exception_and_removed_app_disappears(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / 'apps.txt'
            manifest.write_text('com.example.new\n')
            payload = build.generate(manifest, self.templates, self.stock)
            nodes = ET.fromstring(payload)
            self.assertEqual(nodes[-1].attrib, {'pkg': 'com.example.new', 'use_kill': 'true'})
            self.assertFalse(any(e.get('pkg') == 'com.discord' for e in nodes))

    def test_invalid_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'apps.txt'
            for text in ['com.example.duplicate\ncom.example.duplicate\n', 'com.example.bad" injected="yes\n']:
                path.write_text(text)
                with self.assertRaises(subprocess.CalledProcessError):
                    build.generate(path, self.templates, self.stock)


if __name__ == '__main__':
    unittest.main()
