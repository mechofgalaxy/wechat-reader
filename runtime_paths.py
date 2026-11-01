"""Per-user state and pinned public model metadata; no machine-specific paths."""
import os
from pathlib import Path

MODELS = {
    'turbo': ('mlx-community/whisper-large-v3-turbo', 'a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb'),
    'large-v3': ('mlx-community/whisper-large-v3-mlx', '49e6aa286ad60c14352c404340ded53710378a11'),
}

def same_path(first, second):
    """Compare existing filesystem identities as well as normalized spellings."""
    first=Path(first).expanduser().resolve();second=Path(second).expanduser().resolve()
    if first==second:return True
    try:return first.samefile(second)
    except OSError:return False

def path_within(root, candidate):
    """Containment follows symlinks and filesystem identity (including APFS casing)."""
    root=Path(root).expanduser().resolve();candidate=Path(candidate).expanduser().resolve()
    if candidate==root or root in candidate.parents:return True
    try:
        info=root.stat();identity=(info.st_dev,info.st_ino)
    except OSError:return False
    for ancestor in (candidate,*candidate.parents):
        try:info=ancestor.stat()
        except OSError:continue
        if (info.st_dev,info.st_ino)==identity:return True
    return False

def state_root():
    return Path(os.environ.get('WECHAT_READER_HOME', str(Path.home()/'.local/share/wechat-reader'))).expanduser().resolve()

def model_path(name):
    return state_root()/'models'/name/MODELS[name][1]
