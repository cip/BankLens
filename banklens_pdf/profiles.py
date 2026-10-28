"""Data-only, immutable profile revisions; no statement values or executable rules."""
from pathlib import Path
import hashlib
import json
import re
import threading
import uuid

BUNDLED = Path(__file__).with_name('profiles')
STORE_LOCK = threading.RLock()
MAX_PROFILE = 16_000_000


def read_json(path):
    if path.is_symlink() or path.stat().st_size > MAX_PROFILE:
        raise ValueError('invalid_profile')
    return json.loads(path.read_text(encoding='utf-8'))


class ProfileStore:
    def __init__(self, review):
        self.review = review
        self.directory = review.state_directory / 'profiles'

    def load(self, reference):
        if reference == 'examples':
            return self.review.learn(self.review.load_workspace())
        if reference == 'legacy':
            return self.review.validate_profile(read_json(self.review.profile_path))
        if reference == 'bundled:bank-austria:1':
            path = BUNDLED / 'bank-austria.json'
        else:
            match = re.fullmatch(r'local:([a-f0-9]{32}):([1-9][0-9]{0,8})', reference or '')
            if not match:
                raise ValueError('invalid_profile_reference')
            path = self.directory / match[1] / (match[2] + '.json')
            if self.directory.is_symlink() or path.parent.is_symlink():
                raise ValueError('invalid_profile')
        envelope = read_json(path)
        if envelope.get('catalog_schema_version') != 1:
            raise ValueError('invalid_profile_version')
        if reference != f"{'bundled' if path.parent == BUNDLED else 'local'}:{envelope.get('id')}:{envelope.get('revision')}":
            raise ValueError('invalid_profile_reference')
        return self.review.validate_profile(envelope['profile'])

    def metadata(self, reference, profile=None):
        if profile is None:
            profile = self.load(reference)
        origin = reference.split(':')[0]
        return {'reference': reference, 'name': profile['profile_name'],
                'origin': origin, 'revision': int(reference.split(':')[-1]) if ':' in reference else None,
                'schema_version': profile['schema_version'], 'engine': profile['engine'],
                'sha256': hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()}

    def catalog(self):
        references = ['examples', 'bundled:bank-austria:1']
        if self.review.profile_path.exists():
            references.append('legacy')
        if self.directory.exists() and not self.directory.is_symlink():
            for folder in sorted(self.directory.iterdir()):
                if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'[a-f0-9]{32}', folder.name):
                    continue
                for path in sorted(folder.iterdir()):
                    if re.fullmatch(r'[1-9][0-9]{0,8}\.json', path.name):
                        references.append(f'local:{folder.name}:{path.stem}')
        items, invalid = [], 0
        for reference in references:
            try:
                items.append(self.metadata(reference))
            except (ValueError, OSError, KeyError, TypeError):
                invalid += 1
        return {'profiles': items, 'selected_profile': self.review.selected_profile,
                'invalid_profiles': invalid}

    def save(self, profile):
        """Append a revision only for the same local name; copies get new IDs."""
        self.review.validate_profile(profile)
        with STORE_LOCK:
            selected = self.review.selected_profile
            if selected.startswith('local:') and self.load(selected)['profile_name'] == profile['profile_name']:
                identifier = selected.split(':')[1]
            else:
                identifier = uuid.uuid4().hex
            folder = self.directory / identifier
            if self.directory.is_symlink() or folder.is_symlink():
                raise ValueError('invalid_profile')
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            folder.mkdir(mode=0o700, exist_ok=True)
            revision = max((int(p.stem) for p in folder.iterdir() if re.fullmatch(r'[1-9][0-9]{0,8}\.json', p.name)), default=0) + 1
            while True:
                envelope = {'catalog_schema_version': 1, 'id': identifier, 'revision': revision, 'profile': profile}
                try:
                    self.review.private_write(folder / f'{revision}.json', envelope, overwrite=False)
                    break
                except FileExistsError:
                    revision += 1
            reference = f'local:{identifier}:{revision}'
            self.review.persist_profile_selection(reference)
            return reference
