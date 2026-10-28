Unicode True
Name "BankLens"
OutFile "BankLens-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\BankLens"
RequestExecutionLevel user

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
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
