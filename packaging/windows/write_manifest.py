"""Record paths and hashes of the exact staged installer payload."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
target = root / 'Paketinhalt.json'
entries = []
for path in sorted(root.rglob('*')):
    if not path.is_file() or path == target:
        continue
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    entries.append({'path': path.relative_to(root).as_posix(), 'sha256': digest.hexdigest()})
target.write_text(json.dumps(entries, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
