"""Independent platform-specific assertions for generated private files."""
import json
import os
import subprocess
import shutil


def assert_private(test, path):
    if os.name != "nt":
        test.assertEqual(path.stat().st_mode & 0o777, 0o600)
        return
    script = r'''
      $ErrorActionPreference = 'Stop'
      $acl = Get-Acl -LiteralPath $env:BANKLENS_TEST_FILE
      $rules = @($acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]) | ForEach-Object {
        @{ sid=$_.IdentityReference.Value; type=$_.AccessControlType.ToString();
           rights=[int64]$_.FileSystemRights; inherited=$_.IsInherited }
      })
      @{ protected=$acl.AreAccessRulesProtected; rules=$rules } | ConvertTo-Json -Depth 4 -Compress
    '''
    env = dict(os.environ, BANKLENS_TEST_FILE=str(path))
    executable = shutil.which("pwsh") or "powershell"
    result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, env=env, check=False)
    test.assertEqual(result.returncode, 0, result.stderr)
    acl = json.loads(result.stdout)
    test.assertTrue(acl["protected"], "Windows ACL must block inheritance")
    rules = acl["rules"]
    test.assertEqual({rule["sid"] for rule in rules}, {"S-1-3-4", "S-1-5-18", "S-1-5-32-544"})
    for rule in rules:
        test.assertEqual(rule["type"], "Allow")
        test.assertFalse(rule["inherited"])
        test.assertEqual(rule["rights"] & 0x1f01ff, 0x1f01ff)
