"""Check preserved vendor resources and native dependency provenance."""
import ast
import hashlib
from importlib import util
from pathlib import Path


def verify():
    root = Path('dist/BankLens/_internal')
    for package, relative in (
        ('webview', 'lib/pywebview-android.jar'),
        ('reportlab', 'fonts/hb-test.ttf'),
    ):
        original = Path(util.find_spec(package).origin).parent / relative
        bundled = root / package / relative
        if not bundled.is_file() or original.read_bytes() != bundled.read_bytes():
            raise RuntimeError(f'Vendor resource missing or modified: {package}/{relative}')

    def inspect(node):
        if not isinstance(node, (tuple, list)):
            return
        if (len(node) == 3 and isinstance(node[1], str)
                and node[2] in ('BINARY', 'EXTENSION')):
            parts = Path(node[1]).parts
            if any(part.lower() == 'java' or part.lower().startswith(('jdk', 'temurin', 'eclipse-temurin'))
                   for part in parts):
                raise RuntimeError('Native dependency was collected from a Java installation')
        for child in node:
            inspect(child)

    inspect(ast.literal_eval(Path('build/BankLens/Analysis-00.toc').read_text(encoding='utf-8')))
    font = root / 'reportlab/fonts/hb-test.ttf'
    # Bind the separately supplied OFL notice to the reviewed Noto Sans Khmer subset.
    if hashlib.sha256(font.read_bytes()).hexdigest() != '4df8840ec8382efa2c06bda01e31e1a5a975cd46e13f7c0b0be696a8542f1ba0':
        raise RuntimeError('ReportLab test font differs from the reviewed Noto Sans Khmer subset')


if __name__ == '__main__':
    verify()
