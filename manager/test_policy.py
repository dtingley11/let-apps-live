#!/usr/bin/env python3
"""Exercise list ownership and selection logic without Android or personal data."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='let-apps-live-policy-tests-') as temporary:
    subprocess.run(['javac', '--release', '17', '-d', temporary,
                    str(ROOT / 'src/io/github/dtingley11/letappslive/PolicyEngine.java'),
                    str(ROOT / 'tests/PolicyEngineTest.java')], check=True)
    subprocess.run(['java', '-ea', '-cp', temporary,
                    'io.github.dtingley11.letappslive.PolicyEngineTest'], check=True)
