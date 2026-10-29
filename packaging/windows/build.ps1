$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
$pipReport = Join-Path $env:TEMP "banklens-pip-report-$PID.json"
python -m pip install --force-reinstall --report $pipReport -r packaging/windows/requirements.txt
if ($LASTEXITCODE) { exit $LASTEXITCODE }
# Resolve native dependencies only from the selected Python and Windows installation.
$pythonRoot = python -c "import sys; print(sys.base_prefix)"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$gitBin = Split-Path (Get-Command git).Source
$nsisBin = Split-Path (Get-Command makensis).Source
$env:PATH = "$gitBin;$nsisBin;$pythonRoot;$pythonRoot/Scripts;$env:SystemRoot/System32;$env:SystemRoot"
python -m PyInstaller --noconfirm --clean --windowed --onedir --name BankLens --paths . --add-data 'banklens_pdf/web;banklens_pdf/web' --add-data 'banklens_pdf/profiles;banklens_pdf/profiles' --collect-all pypdfium2 --collect-data reportlab packaging/windows/desktop_entry.py
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$pythonRuntime = Join-Path $pythonRoot 'VCRUNTIME140.dll'
$bundledRuntime = 'dist/BankLens/_internal/VCRUNTIME140.dll'
if (!(Test-Path $bundledRuntime) -or (Get-FileHash $pythonRuntime).Hash -ne (Get-FileHash $bundledRuntime).Hash) {
    throw 'Die Microsoft-C-Laufzeit fehlt oder weicht von der Python-Installation ab.'
}
$javaRuntime = @(Get-ChildItem 'dist/BankLens' -File -Recurse | Where-Object { $_.Name -match '^(?i:jvm\.dll|java(?:w)?\.exe)$' })
if ($javaRuntime.Count) { throw 'Unerwartete Java-Laufzeit im Paket.' }
python packaging/windows/verify_vendor_files.py
if ($LASTEXITCODE) { exit $LASTEXITCODE }
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
