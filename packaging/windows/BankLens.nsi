Unicode True
SetCompressor zlib
Name "BankLens"
OutFile "BankLens-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\BankLens"
RequestExecutionLevel user

!define VC_RUNTIME_DOWNLOAD "https://aka.ms/vc14/vc_redist.x64.exe"

Function .onInit
  SetRegView 64
  ReadRegDWORD $0 HKLM "SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" "Installed"
  StrCmp $0 1 runtime_present
  MessageBox MB_ICONEXCLAMATION|MB_YESNO \
    "BankLens benoetigt Microsoft Visual C++ 2015-2022 Redistributable (x64), das auf diesem PC nicht gefunden wurde.$\r$\n$\r$\nSoll der offizielle Microsoft-Installer jetzt heruntergeladen werden? Installiere die Laufzeit und starte danach BankLens-Setup erneut." \
    IDYES download_runtime IDNO cancel_install
  download_runtime:
    ExecShell "open" "${VC_RUNTIME_DOWNLOAD}"
  cancel_install:
    Abort
  runtime_present:
FunctionEnd

Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "BankLens"
  SetOutPath "$INSTDIR"
  File /r "..\..\dist\BankLens\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\BankLens"
  CreateShortcut "$SMPROGRAMS\BankLens\BankLens.lnk" "$INSTDIR\BankLens.exe"
  CreateShortcut "$SMPROGRAMS\BankLens\Deinstallieren.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BankLens" "DisplayName" "BankLens"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BankLens" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\BankLens\BankLens.lnk"
  Delete "$SMPROGRAMS\BankLens\Deinstallieren.lnk"
  RMDir "$SMPROGRAMS\BankLens"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\BankLens"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\BankLens.exe"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\COPYRIGHT.md"
  Delete "$INSTDIR\Quellcode-Commit.txt"
  Delete "$INSTDIR\BankLens-Quellcode.zip"
  Delete "$INSTDIR\Paketinhalt.json"
  RMDir /r "$INSTDIR\Lizenzen"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
