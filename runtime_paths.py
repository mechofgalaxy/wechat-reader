"""Per-user state and pinned public model metadata; no machine-specific paths."""
import os
from pathlib import Path

MODELS = {
    'turbo': ('mlx-community/whisper-large-v3-turbo', 'a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb'),
    'large-v3': ('mlx-community/whisper-large-v3-mlx', '49e6aa286ad60c14352c404340ded53710378a11'),
}

def state_root():
    return Path(os.environ.get('WECHAT_READER_HOME', str(Path.home()/'.local/share/wechat-reader'))).expanduser().resolve()

def model_path(name):
    return state_root()/'models'/name/MODELS[name][1]
