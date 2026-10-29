$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
$pipReport = Join-Path $env:TEMP "banklens-pip-report-$PID.json"
python -m pip install --force-reinstall --report $pipReport -r packaging/windows/requirements.txt
if ($LASTEXITCODE) { exit $LASTEXITCODE }
python -m PyInstaller --noconfirm --clean --windowed --onedir --name BankLens --paths . --add-data 'banklens_pdf/web;banklens_pdf/web' --add-data 'banklens_pdf/profiles;banklens_pdf/profiles' --collect-all pypdfium2 --collect-data reportlab packaging/windows/desktop_entry.py
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
$smoke = Start-Process -FilePath (Resolve-Path 'dist/BankLens/BankLens.exe') -ArgumentList '--self-test' -Wait -PassThru
if ($smoke.ExitCode -ne 0) { throw "Bundled application self-test failed: exit $($smoke.ExitCode)" }
& makensis packaging/windows/BankLens.nsi
if ($LASTEXITCODE) { exit $LASTEXITCODE }
