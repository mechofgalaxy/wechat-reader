"""Bounded local image decoding. No key discovery, network, or WeChat writes.

V1/V2 segmentation reference: r266-tech/wx-cli main.go at d833d687.
The implementation uses macOS CommonCrypto, ImageIO and Vision directly.
"""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import platform
import stat
import struct
import subprocess
import tempfile
from runtime_paths import path_within

MAX_BYTES = 64 * 1024 * 1024
NATIVE = Path(__file__).resolve().with_name('image_native')
V1 = b'\x07\x08V1\x08\x07'
V2 = b'\x07\x08V2\x08\x07'

class ImageError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def image_format(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
    if data.startswith(b'\xff\xd8\xff'): return 'jpeg'
    if data[:6] in (b'GIF87a', b'GIF89a'): return 'gif'
    if data.startswith(b'BM'): return 'bmp'
    if data[:4] in (b'II*\x00', b'MM\x00*'): return 'tiff'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return 'webp'
    if len(data) >= 12 and data[4:8] == b'ftyp' and data[8:12] in (b'heic', b'heix', b'hevc', b'hevx', b'mif1', b'avif'): return 'heif'
    if data.startswith(b'wxgf'): return 'wxgf'
    return None

def aes_ecb(data, key, decrypt=True):
    """Key stays in memory; never appears in argv, environment or diagnostics."""
    if platform.system() != 'Darwin': raise ImageError('aes_runtime_unavailable')
    if len(key) != 16 or not data or len(data) % 16: raise ImageError('invalid_encrypted_layout')
    try:
        lib = ctypes.CDLL('/usr/lib/system/libcommonCrypto.dylib')
        fn = lib.CCCrypt
        fn.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                       ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                       ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        fn.restype = ctypes.c_int32
        keybuf = ctypes.create_string_buffer(key)
        source = ctypes.create_string_buffer(data)
        target = ctypes.create_string_buffer(len(data) + 16)
        moved = ctypes.c_size_t()
        code = fn(1 if decrypt else 0, 0, 2, keybuf, 16, None,
                  source, len(data), target, len(target), ctypes.byref(moved))
        if code: raise ImageError('aes_decode_failed')
        return target.raw[:moved.value]
    except (OSError, AttributeError):
        raise ImageError('aes_runtime_unavailable') from None

def unpad(data):
    n = data[-1] if data else 0
    if not 1 <= n <= 16 or data[-n:] != bytes([n]) * n: raise ImageError('image_key_or_data_invalid')
    return data[:-n]

def key_material(config, access_material):
    """Use only explicit fields already supplied to this selected profile."""
    source = config
    if config.get('image_key_file'):
        p = Path(str(config['image_key_file'])).expanduser()
        try:
            if p.is_symlink(): raise ImageError('unsafe_image_key_file')
            fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077: raise ImageError('unsafe_image_key_file')
                if info.st_size > 65536: raise ImageError('invalid_image_key_file')
                raw = stream.read(65537)
                if len(raw) > 65536: raise ImageError('invalid_image_key_file')
                source = json.loads(raw)
            if not isinstance(source, dict): raise ImageError('invalid_image_key_file')
            if config.get('_image_binding_required') and source.get('account_binding') != config['_image_binding_required']:
                raise ImageError('image_access_profile_mismatch')
        except (OSError, ValueError): raise ImageError('invalid_image_key_file') from None
    elif not (source.get('image_aes_key') or source.get('image_key')):
        source = access_material
    key = source.get('image_aes_key') or source.get('image_key')
    if key:
        try:
            if not isinstance(key, str): raise ValueError()
            if key.startswith('hex:'): result = bytes.fromhex(key[4:])
            elif len(key) == 32: result = bytes.fromhex(key)
            else: result = key.encode('ascii')
            if len(result) != 16: raise ValueError()
        except (ValueError, UnicodeError): raise ImageError('invalid_image_key') from None
    else:
        result = None
    xor = config.get('image_xor_key', source.get('image_xor_key'))
    if xor is not None and (isinstance(xor, bool) or not isinstance(xor, int) or not 0 <= xor <= 255):
        raise ImageError('invalid_image_xor_key')
    return result, xor

def decode_bytes(data, aes_key=None, xor_key=None):
    if not data or len(data) > MAX_BYTES: raise ImageError('invalid_image_size')
    kind = image_format(data)
    if kind: return data, {'encoding': 'plain', 'format': kind}
    if data[:6] in (V1, V2):
        if len(data) < 15: raise ImageError('invalid_encrypted_layout')
        prefix_size, tail_size = struct.unpack_from('<II', data, 6)
        encrypted_size = ((prefix_size // 16) + 1) * 16 if prefix_size else 0
        if encrypted_size > len(data)-15 or tail_size > len(data)-15-encrypted_size:
            raise ImageError('invalid_encrypted_layout')
        key = b'cfcd208495d565ef' if data[:6] == V1 else aes_key
        if encrypted_size and not key: raise ImageError('image_key_required')
        middle_end = len(data) - tail_size
        head = unpad(aes_ecb(data[15:15+encrypted_size], key)) if encrypted_size else b''
        if len(head) != prefix_size: raise ImageError('invalid_encrypted_layout')
        if tail_size and xor_key is None:
            # JPEG EOI allows an exact two-byte consistency check, not a default guess.
            a, b = data[-2] ^ 0xff, data[-1] ^ 0xd9
            if tail_size >= 2 and a == b and head.startswith(b'\xff\xd8\xff'):
                xor_key = a
            else:
                raise ImageError('image_xor_key_required')
        tail = bytes(v ^ (xor_key or 0) for v in data[middle_end:]) if tail_size else b''
        decoded = head + data[15+encrypted_size:middle_end] + tail
        kind = image_format(decoded)
        if not kind: raise ImageError('image_key_or_data_invalid')
        return decoded, {'encoding': 'wechat_v1' if data[:6] == V1 else 'wechat_v2', 'format': kind}
    for signature in (b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'GIF87a', b'GIF89a', b'BM', b'II*\x00', b'MM\x00*', b'RIFF'):
        if len(data) < len(signature): continue
        key = data[0] ^ signature[0]
        if all(data[i] ^ key == v for i,v in enumerate(signature)):
            decoded = bytes(v ^ key for v in data)
            kind = image_format(decoded)
            if kind: return decoded, {'encoding': 'wechat_xor', 'format': kind}
    raise ImageError('unsupported_image_encoding')

def within(path, roots):
    return any(path_within(root,path) for root in roots)

def read_source(path, roots):
    resolved = path.expanduser().resolve()
    allowed = [p.expanduser().resolve() for p in roots]
    if not allowed or not within(resolved, allowed): raise ImageError('image_outside_selected_profile')
    try:
        fd = os.open(resolved, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode): raise ImageError('not_regular_image_file')
            if before.st_size <= 0 or before.st_size > MAX_BYTES: raise ImageError('invalid_image_size')
            data = stream.read(MAX_BYTES+1)
            after = os.fstat(stream.fileno())
            current = resolved.stat()
        identity = lambda s:(s.st_ino,s.st_size,s.st_mtime_ns)
        if identity(before) != identity(after) or identity(after) != identity(current): raise ImageError('image_changed_during_read')
        return resolved, data
    except FileNotFoundError: raise ImageError('image_not_downloaded') from None
    except OSError: raise ImageError('image_source_unreadable') from None

def run_native(data, output, ocr):
    if not NATIVE.is_file(): raise ImageError('image_runtime_unavailable')
    mode = 'ocr' if ocr else 'render' if output else 'inspect'
    try:
        p = subprocess.run([str(NATIVE), mode, str(output) if output else '-'], input=data, capture_output=True, timeout=60)
        result = json.loads(p.stdout)
        if p.returncode or not result.get('ok'): raise ImageError(result.get('code','image_decode_failed'))
        return result
    except subprocess.TimeoutExpired: raise ImageError('image_processing_timeout') from None
    except (OSError, ValueError): raise ImageError('image_runtime_failed') from None

def process_image(source, roots, config, access_material, output=None, ocr=False, expected_md5=None):
    result = {'status': 'unverified', 'ready': False, 'source_scope': 'selected_profile_resource_roots',
              'source_modified': False, 'network_used': False, 'key_acquisition': False,
              'variant': 'thumbnail' if source.stem.endswith('_t') else 'high_definition' if source.stem.endswith('_h') else 'standard_or_unknown'}
    try:
        source, data = read_source(source, roots)
        result['source_bytes'] = len(data)
        # Ordinary and XOR images do not depend on optional AES settings.
        key, xor = key_material(config, access_material) if data[:6] in (V1,V2) else (None,None)
        decoded, info = decode_bytes(data, key, xor)
        result.update(info)
        if expected_md5 is not None:
            if len(expected_md5)!=32 or any(c not in '0123456789abcdefABCDEF' for c in expected_md5): raise ImageError('invalid_expected_md5')
            if hashlib.md5(decoded).hexdigest()!=expected_md5.lower(): raise ImageError('image_digest_mismatch')
            result['resource_digest_verified'] = True
        else:
            result['resource_digest_verified'] = False
        pixels, conversion = pixel_payload(decoded, info['format'])
        result.update(conversion)
        if output:
            output = output.expanduser().absolute()
            if output.suffix.lower() != '.png': raise ImageError('output_must_be_png')
            if output.is_symlink() or output.exists(): raise ImageError('output_exists')
            if not output.parent.is_dir(): raise ImageError('output_directory_missing')
            resolved_parent = output.parent.resolve()
            if within(resolved_parent, [p.expanduser().resolve() for p in roots]): raise ImageError('output_inside_wechat_source')
            # Private staging plus exclusive atomic hardlink prevents overwrite races.
            with tempfile.TemporaryDirectory(prefix='.wechat-image-',dir=resolved_parent) as temp:
                staging = Path(temp)/'preview.png'
                native = run_native(pixels, staging, ocr)
                os.chmod(staging,0o600)
                try: os.link(staging, resolved_parent/output.name)
                except FileExistsError: raise ImageError('output_exists') from None
                result['output_path'] = str(resolved_parent/output.name)
        else:
            native = run_native(pixels,None,ocr)
        native.pop('ok',None)
        result.update(native)
        if conversion.get('wxgf_first_frame_only'):
            result['frame_count'] = None
        result.update(status='ready',ready=True)
        if ocr and result.get('ocr',{}).get('status')!='ok': result['status']='image_ready_ocr_failed'
    except ImageError as exc:
        result['status'] = exc.code
    except OSError:
        result['status'] = 'image_io_failed'
    return result

# Explicit, disk-only setup. It never runs from an ordinary image read.
def selected_account(config, roots):
    session = Path(str(config.get('session_db', ''))).expanduser().resolve()
    storage = next((p for p in session.parents if p.name == 'db_storage'), None)
    if storage is None or storage.parent.parent.name != 'xwechat_files':
        raise ImageError('image_account_layout_unverified')
    account = storage.parent
    username = str(config.get('self_username') or '')
    if not username or account.name.rsplit('_', 1)[0] != username:
        raise ImageError('image_account_identity_mismatch')
    paths = [Path(str(p)).expanduser().resolve() for p in config.get('message_dbs', [])]
    paths += [p.expanduser().resolve() for p in roots]
    if not paths or not all(within(p, [account]) for p in paths):
        raise ImageError('image_account_paths_mixed')
    binding = hashlib.sha256((str(account)+'\n'+username).encode()).hexdigest()
    return account, username, binding

def access_path(profile):
    p = profile.expanduser().resolve()
    return p.with_name(p.stem+'.image-access.json')

def profile_image_config(config, roots, profile):
    result = dict(config)
    if not any(config.get(k) for k in ('image_key_file','image_aes_key','image_key')):
        p = access_path(profile)
        if p.exists() or p.is_symlink():
            result['image_key_file'] = str(p)
            result['_image_binding_required'] = selected_account(config, roots)[2]
    return result

def image_access(config, roots, profile, samples, save=False):
    result = {'ready':False, 'status':'unverified', 'method':'selected_container_statistics_filenames',
              'process_access':False, 'network_used':False, 'wechat_modified':False,
              'profile_modified':False, 'material_written':False}
    try:
        import re
        account, username, binding = selected_account(config, roots)
        if not 2 <= len(samples) <= 6: raise ImageError('image_setup_requires_2_to_6_samples')
        payloads = []
        identities = set()
        for p in samples:
            _, raw = read_source(p, roots)
            if not raw.startswith(V2): raise ImageError('image_setup_requires_v2_samples')
            identities.add(hashlib.sha256(raw).digest())
            payloads.append(raw)
        if len(identities) != len(samples): raise ImageError('image_setup_requires_distinct_samples')
        docs = account.parent.parent
        stats = docs/'app_data'
        if stats.resolve() != stats: raise ImageError('image_statistics_path_redirected')
        codes = set()
        matched = 0
        for suffix in ('net/kvcomm','ilink/kvcomm'):
            directory = stats/suffix
            if directory.resolve() != directory: raise ImageError('image_statistics_path_redirected')
            if not directory.is_dir(): continue
            for i, path in enumerate(directory.iterdir()):
                if i >= 4096: raise ImageError('image_statistics_limit_exceeded')
                m = re.fullmatch(r'key_([0-9]{1,10})_.*\.statistic', path.name)
                if m and not path.is_symlink() and path.is_file():
                    number = int(m[1])
                    if 0 < number <= 0xffffffff:
                        codes.add(number);matched += 1
                if len(codes) > 64: raise ImageError('image_statistics_limit_exceeded')
        result.update(candidate_count=len(codes), matching_filename_count=matched)
        if not codes: raise ImageError('image_statistics_not_available')
        verified = []
        for number in sorted(codes):
            key = hashlib.md5((str(number)+username).encode()).hexdigest()[:16].encode('ascii')
            xor = number & 255
            proofs = []
            try:
                for raw in payloads:
                    decoded, info = decode_bytes(raw,key,xor)
                    pixels, conversion = pixel_payload(decoded,info['format'])
                    native = run_native(pixels,None,False)
                    proofs.append({'format':info['format'],'width':native['width'],'height':native['height'],
                                   'pixel_decode_verified':True,**conversion})
            except ImageError:
                continue
            verified.append((key,xor,proofs))
        if len(verified) != 1:
            raise ImageError('image_key_not_verified' if not verified else 'image_key_ambiguous')
        key, xor, proofs = verified[0]
        result.update(ready=True,status='verified',validated_samples=proofs)
        if save:
            dest = access_path(profile)
            if within(dest.parent, [account]): raise ImageError('image_access_inside_wechat_source')
            content = {'schema_version':1,'account_binding':binding,'image_aes_key':key.decode('ascii'),
                       'image_xor_key':xor,'method':result['method'],'validated_sample_count':len(proofs)}
            encoded = (json.dumps(content,sort_keys=True)+'\n').encode()
            # Existing material is deliberately never overwritten, including symlinks.
            with tempfile.TemporaryDirectory(prefix='.image-access-',dir=dest.parent) as temp:
                p = Path(temp)/'material.json'
                fd = os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'wb') as f:
                    f.write(encoded);f.flush();os.fsync(f.fileno())
                try: os.link(p,dest)
                except FileExistsError: raise ImageError('image_access_already_exists') from None
            result.update(status='ready',material_written=True,material_path=str(dest))
    except ImageError as exc:
        result.update(ready=False,status=exc.code)
    except OSError:
        result.update(ready=False,status='image_access_io_failed')
    return result

import sys
MEDIA_WORKER = Path(__file__).resolve().with_name('media_worker.py')

def pixel_payload(decoded, kind):
    if kind != 'wxgf': return decoded, {}
    import re
    match = re.search(b'\x00\x00\x00\x01\x40\x01|\x00\x00\x01\x40\x01', decoded[:4096])
    if not match: raise ImageError('wxgf_bitstream_not_found')
    stream = decoded[match.start():]
    if not all(re.search(b'\x00\x00\x01'+bytes([nal << 1,1]),stream[:65536]) for nal in (33,34)):
        raise ImageError('wxgf_parameter_sets_missing')
    if not MEDIA_WORKER.is_file(): raise ImageError('wxgf_converter_required')
    try:
        proc = subprocess.run([sys.executable,'-I',str(MEDIA_WORKER)],input=stream,capture_output=True,timeout=30)
        if proc.returncode==3:raise ImageError('wxgf_converter_required')
        if proc.returncode or not proc.stdout or len(proc.stdout)>MAX_BYTES or image_format(proc.stdout)!='png':
            raise ImageError('wxgf_decode_failed')
        return proc.stdout, {'wxgf_first_frame_only':True, 'decoded_format':'png','source_frame_count_verified':False}
    except subprocess.TimeoutExpired: raise ImageError('image_processing_timeout') from None
    except (OSError,ValueError,TypeError): raise ImageError('wxgf_decode_failed') from None
