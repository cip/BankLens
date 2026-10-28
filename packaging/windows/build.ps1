$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
python -m pip install -r packaging/windows/requirements.txt
if ($LASTEXITCODE) { exit $LASTEXITCODE }
python -m PyInstaller --noconfirm --clean --windowed --onedir --name BankLens --paths . --add-data 'banklens_pdf/web;banklens_pdf/web' --collect-all pypdfium2 --collect-data reportlab packaging/windows/desktop_entry.py
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& makensis packaging/windows/BankLens.nsi
if ($LASTEXITCODE) { exit $LASTEXITCODE }
