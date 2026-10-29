$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
$pipReport = Join-Path $env:TEMP "banklens-pip-report-$PID.json"
python -m pip install --force-reinstall --report $pipReport -r packaging/windows/requirements.txt
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$env:PATH = (($env:PATH -split ';') | Where-Object { $_ -notmatch '(?i)java|jdk|jre' }) -join ';'
python -m PyInstaller --noconfirm --clean --windowed --onedir --name BankLens --paths . --add-data 'banklens_pdf/web;banklens_pdf/web' --add-data 'banklens_pdf/profiles;banklens_pdf/profiles' --collect-all pypdfium2 --collect-data reportlab packaging/windows/desktop_entry.py
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$unexpectedRuntime = @(Get-ChildItem 'dist/BankLens/_internal' -File | Where-Object { $_.Name -match '^(?i:api-ms-win-.*|ucrtbase)\.dll$' })
if ($unexpectedRuntime.Count) { $unexpectedRuntime | Remove-Item -Force }
$bundledRuntime = @(Get-ChildItem 'dist/BankLens' -File -Recurse | Where-Object { $_.Name -match '^(?i:VCRUNTIME.*)\.dll$' })
if ($bundledRuntime.Count) { $bundledRuntime | Remove-Item -Force }
$androidJar = 'dist/BankLens/_internal/webview/lib/pywebview-android.jar'
if (Test-Path $androidJar) { Remove-Item $androidJar -Force }
$testFont = 'dist/BankLens/_internal/reportlab/fonts/hb-test.ttf'
if (Test-Path $testFont) { Remove-Item $testFont -Force }
$javaComponents = @(Get-ChildItem 'dist/BankLens' -File -Recurse | Where-Object { $_.Name -match '^(?i:jvm\.dll|java(?:w)?\.exe)$' -or $_.Extension -ieq '.jar' })
if ($javaComponents.Count) { throw 'Unerwartete Java-Komponente im Paket.' }
$bundledRuntime = @(Get-ChildItem 'dist/BankLens' -File -Recurse | Where-Object { $_.Name -match '^(?i:VCRUNTIME.*)\.dll$' })
if ($bundledRuntime.Count) { throw 'Microsoft Visual C++ Runtime darf nicht im Paket enthalten sein.' }
Copy-Item LICENSE 'dist/BankLens/LICENSE.txt'
Copy-Item COPYRIGHT.md 'dist/BankLens/COPYRIGHT.md'
python packaging/windows/collect_licenses.py 'dist/BankLens/Lizenzen' $pipReport
if ($LASTEXITCODE) { exit $LASTEXITCODE }
Remove-Item $pipReport -Force
git diff --quiet
if ($LASTEXITCODE) { throw 'Quellcode hat uncommittete Änderungen.' }
git diff --cached --quiet
if ($LASTEXITCODE) { throw 'Quellcode hat uncommittete Änderungen.' }
git rev-parse HEAD | Set-Content -Encoding utf8 'dist/BankLens/Quellcode-Commit.txt'
if ($LASTEXITCODE) { exit $LASTEXITCODE }
git archive --format=zip --output=dist/BankLens/BankLens-Quellcode.zip HEAD
if ($LASTEXITCODE) { exit $LASTEXITCODE }
python packaging/windows/write_manifest.py 'dist/BankLens'
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$sourceProfile = 'banklens_pdf/profiles/bank-austria.json'
$bundledProfile = 'dist/BankLens/_internal/banklens_pdf/profiles/bank-austria.json'
if (!(Test-Path $bundledProfile) -or (Get-FileHash $sourceProfile).Hash -ne (Get-FileHash $bundledProfile).Hash) {
    throw 'Bundled bank profile is missing or differs from the source.'
}
$smoke = Start-Process -FilePath (Resolve-Path 'dist/BankLens/BankLens.exe') -ArgumentList '--self-test' -PassThru
if (!$smoke.WaitForExit(120000)) {
    $smoke.Kill()
    throw 'Bundled application self-test timed out after 120 seconds.'
}
if ($smoke.ExitCode -ne 0) { throw "Bundled application self-test failed: exit $($smoke.ExitCode)" }
& makensis packaging/windows/BankLens.nsi
if ($LASTEXITCODE) { exit $LASTEXITCODE }
