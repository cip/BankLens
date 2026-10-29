"""Collect notices for the pinned Windows build; never download during packaging."""
from importlib import metadata, util
import hashlib
import json
from pathlib import Path
import shutil
import sys

PACKAGES = {
    'pypdf': '6.10.0', 'pypdfium2': '5.14.0', 'Pillow': '12.3.0',
    'reportlab': '4.4.9', 'charset-normalizer': '3.5.2', 'pywebview': '5.4',
    'pythonnet': '3.2.1', 'proxy_tools': '0.1.0', 'bottle': '0.13.4',
    'typing_extensions': '4.16.0', 'clr_loader': '0.3.1', 'cffi': '2.1.1',
    'pycparser': '3.12', 'altgraph': '0.17.5', 'PyInstaller': '6.11.1',
    'pyinstaller-hooks-contrib': '2026.9', 'packaging': '26.3',
    'pefile': '2023.2.7', 'pywin32-ctypes': '0.2.3', 'setuptools': '80.10.2',
}
WEBVIEW_DLLS = {
    'Microsoft.Web.WebView2.Core.dll': 'cb8c852fcc4ef55d630b64d171dc11538bb25258041ed22cf31735982a2e09e3',
    'Microsoft.Web.WebView2.WinForms.dll': 'e62056bee28ab094071144b47371009a6fbc162f9aea184719f2e86ed515f7f8',
    'runtimes/win-arm64/native/WebView2Loader.dll': '277e84cd9474ef6302ff3bc91706ccac9bc709cd226de4dbd7dad28571b2bc05',
    'runtimes/win-x64/native/WebView2Loader.dll': '271b57e3ec03c436a15d80cafeb9fd1618a43793233d8b05c9446f8de0a51be4',
    'runtimes/win-x86/native/WebView2Loader.dll': '7f362fd98cc243ad620f2d0a4a6c223df80f960c4e19a2d9972f4af7938565cf',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(destination, pip_report=None):
    if sys.version_info[:3] != (3, 11, 9):
        raise RuntimeError('Windows build requires Python 3.11.9')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(__file__).with_name('licenses'), destination / 'zusatz', dirs_exist_ok=True)
    records = []
    for name, expected in PACKAGES.items():
        dist = metadata.distribution(name)
        if dist.version != expected:
            raise RuntimeError(f'Unexpected version of {name}: {dist.version}')
        copied = []
        for item in dist.files or ():
            relative = Path(str(item))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            lowered = str(relative).lower()
            basename = relative.name.lower()
            is_notice = (basename.startswith(('license', 'copying', 'notice'))
                         or ('.dist-info/' in lowered and '/licenses/' in lowered)
                         or (name == 'reportlab' and lowered.startswith('reportlab/fonts/')
                             and basename.endswith('.txt'))
                         or basename.endswith('.cdx.json'))
            if not is_notice:
                continue
            source = Path(dist.locate_file(item))
            if source.is_file():
                target = destination / 'pakete' / name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                copied.append(str(relative).replace('\\', '/'))
        if not copied and name != 'proxy_tools':
            raise RuntimeError(f'No license files found for {name}')
        records.append({'name': name, 'version': dist.version, 'license_files': copied,
                        'declared_license': dist.metadata.get('License-Expression') or dist.metadata.get('License')})
    webview = Path(util.find_spec('webview').origin).parent / 'lib'
    for filename, expected in WEBVIEW_DLLS.items():
        if sha(webview / filename) != expected:
            raise RuntimeError('WebView2 SDK binary differs from the reviewed version')
    proxy = Path(util.find_spec('proxy_tools').origin)
    if sha(proxy) != 'd1539d95e1a713c068ca81d42e047b2c76568964cf277596d4e19efb22f476be':
        raise RuntimeError('proxy_tools source differs from the reviewed version')
    (destination / 'paketversionen.json').write_text(json.dumps(records, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    if pip_report is not None:
        report = json.loads(Path(pip_report).read_text(encoding='utf-8'))
        downloads = []
        for item in report['install']:
            digest = item['download_info']['archive_info']['hashes']['sha256']
            downloads.append({'name': item['metadata']['name'], 'version': item['metadata']['version'], 'sha256': digest})
        if len(downloads) != len(PACKAGES):
            raise RuntimeError('Unexpected pip download inventory')
        (destination / 'paket-downloads.json').write_text(json.dumps(downloads, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    collect(sys.argv[1], sys.argv[2])
