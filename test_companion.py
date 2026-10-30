from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile
import unittest
import re

ROOT = Path(__file__).resolve().parent
VERSION = int(re.search(r'^LAL_VERSION_CODE=(\d+)$', (ROOT / 'module/companion.sh').read_text(), re.M).group(1))


class CompanionTests(unittest.TestCase):
    def trial(self, *, installed=None, granted=False, version=VERSION, install_failure=False,
              install_wrong_hash=False, grant_failure=False, ineffective_grant=False, tampered=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'companion').mkdir()
            apk = root / 'companion/LetAppsLive.apk'
            apk.write_bytes(b'reviewed companion fixture')
            (root / 'resources.sha256').write_text(sha256(apk.read_bytes()).hexdigest()
                                                  + '  companion/LetAppsLive.apk\n')
            if tampered:
                apk.write_bytes(b'changed companion')
            if installed is not None:
                (root / 'installed.apk').write_bytes(apk.read_bytes() if installed == 'match' else b'other APK')
            (root / 'permission').write_text('true' if granted else 'false')
            script = r'''
                MODDIR=$1
                . "$2"
                athena_check() { (cd "$MODDIR" && sha256sum -c resources.sha256 >/dev/null 2>&1); }
                lal_package_path() {
                    [ -f "$MODDIR/installed.apk" ] || return 1
                    printf 'package:%s/installed.apk\n' "$MODDIR"
                }
                lal_package_dump() {
                    [ -f "$MODDIR/installed.apk" ] || return 0
                    printf '    versionCode=%s minSdk=30\n' "$TEST_VERSION"
                    printf '      android.permission.WRITE_SECURE_SETTINGS: granted=%s\n' "$(cat "$MODDIR/permission")"
                }
                lal_install_apk() {
                    printf 'install\n' >> "$MODDIR/calls"
                    [ "$INSTALL_FAIL" = 0 ] || return 1
                    if [ "$INSTALL_WRONG" = 1 ]; then
                        printf 'wrong APK' > "$MODDIR/installed.apk"
                    else
                        cp "$LAL_APK" "$MODDIR/installed.apk"
                    fi
                }
                lal_grant_permission() {
                    printf 'grant\n' >> "$MODDIR/calls"
                    [ "$GRANT_FAIL" = 0 ] || return 1
                    [ "$INEFFECTIVE_GRANT" = 1 ] || printf 'true' > "$MODDIR/permission"
                    return 0
                }
                lal_companion_sync
            '''
            import os
            env = dict(os.environ, TEST_VERSION=str(version), INSTALL_FAIL=str(int(install_failure)),
                       INSTALL_WRONG=str(int(install_wrong_hash)), GRANT_FAIL=str(int(grant_failure)),
                       INEFFECTIVE_GRANT=str(int(ineffective_grant)))
            result = subprocess.run(['sh', '-c', script, 'test', str(root),
                                     str(ROOT / 'module/companion.sh')], env=env,
                                    capture_output=True, text=True)
            calls = (root / 'calls').read_text().splitlines() if (root / 'calls').exists() else []
            return result.returncode, calls, (root / 'permission').read_text(), (root / 'companion-status.txt').read_text()

    def test_verified_installed_and_granted_is_noop(self):
        code, calls, permission, status = self.trial(installed='match', granted=True)
        self.assertEqual((code, calls, permission), (0, [], 'true'))
        self.assertIn('already granted', status)

    def test_new_install_then_grant(self):
        code, calls, permission, status = self.trial()
        self.assertEqual((code, calls, permission), (0, ['install', 'grant'], 'true'))
        self.assertIn('granted and verified', status)

    def test_revoked_permission_is_repaired_without_reinstall(self):
        code, calls, permission, _ = self.trial(installed='match')
        self.assertEqual((code, calls, permission), (0, ['grant'], 'true'))

    def test_install_failure_never_grants_unknown_apk(self):
        code, calls, permission, _ = self.trial(installed='other', version=1, install_failure=True)
        self.assertNotEqual(code, 0)
        self.assertEqual((calls, permission), (['install'], 'false'))

    def test_wrong_installed_hash_never_grants(self):
        code, calls, permission, _ = self.trial(install_wrong_hash=True)
        self.assertNotEqual(code, 0)
        self.assertEqual((calls, permission), (['install'], 'false'))

    def test_newer_app_with_existing_grant_is_preserved(self):
        code, calls, _, status = self.trial(installed='other', version=VERSION + 1, granted=True)
        self.assertEqual((code, calls), (0, []))
        self.assertIn('newer companion retained', status)

    def test_newer_unverified_app_is_not_given_new_permission(self):
        code, calls, permission, _ = self.trial(installed='other', version=VERSION + 1)
        self.assertNotEqual(code, 0)
        self.assertEqual((calls, permission), ([], 'false'))

    def test_tampered_asset_is_rejected_before_package_operations(self):
        code, calls, permission, _ = self.trial(tampered=True)
        self.assertNotEqual(code, 0)
        self.assertEqual((calls, permission), ([], 'false'))

    def test_denied_or_ineffective_grant_is_not_reported_ready(self):
        for option in [{'grant_failure': True}, {'ineffective_grant': True}]:
            with self.subTest(option=option):
                code, calls, permission, status = self.trial(installed='match', **option)
                self.assertNotEqual(code, 0)
                self.assertEqual((calls, permission), (['grant'], 'false'))
                self.assertNotIn('Ready:', status)


if __name__ == '__main__':
    unittest.main()
