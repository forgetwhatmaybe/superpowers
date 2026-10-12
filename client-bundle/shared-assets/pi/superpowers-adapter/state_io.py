"""Strict, silent I/O for the owned Superpowers bootstrap receipt (Python 3.9+)."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid


_HOST = "pi"
_OWNER = "superpowers-adapter"
_REPOSITORY = "superpowers"
_RECORD = "bootstrap-state.json"
_SCHEMA_SHA = "f624783e326e6fd7c09a14c003574fa638983ba4b444a2f591be63d5c9ef41d5"
_DEFINITION_SHA = "17aac94c6fbd0b20efea8cb5cbc7ba53b739bdd69accc3d1f1f695bbb28a62a6"
_BOOTSTRAP_REF = "superpowers/skills/using-superpowers/SKILL.md"
_BOOTSTRAP_RAW_IDENTITIES = frozenset((
    ("30f2ab78e20ddc27ee7158ae8d4a2abe161c360981c7cc3548070913142d3dc3", 3108),
    ("3ff749d00d9baa18813a2ec2a114d09b6c0bf6e9938b030aac617c0ea12added", 3171),
))
_VERSION_RAW = b'{"asset_version":"1.0.0"}\n'
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_REPARSE = 0x400
_REASONS = frozenset((
    "STATE_JSON_INVALID", "STATE_FIELDS_INVALID", "STATE_INTEGER_REQUIRED",
    "STATE_VALUE_INVALID", "STATE_HOST_MISMATCH", "STATE_VERSION_MISMATCH",
    "STATE_SOURCE_MISMATCH", "STATE_GENERATION_STALE", "INTERFACE_JSON_INVALID",
    "INTERFACE_FIELDS_INVALID", "INTERFACE_HOST_MISMATCH", "INTERFACE_EVENT_UNSUPPORTED",
    "INTERFACE_SEQUENCE_STALE", "SOURCE_REFERENCE_INVALID", "SOURCE_BYTES_CHANGED",
    "NATIVE_EXECUTION_UNVERIFIED", "PRODUCER_BINDING_UNKNOWN", "CRAP_SCORE_BLOCKED",
))


class StateRefusal(ValueError):
    """A reason-only refusal; other exceptions are not controlled refusals."""

    def __init__(self, reason_code: str):
        if type(reason_code) is not str or reason_code not in _REASONS:
            raise ValueError("STATE_VALUE_INVALID")
        self.reason_code = reason_code
        super().__init__(reason_code)


def _refuse(reason):
    raise StateRefusal(reason)


def _absolute(path):
    if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
        _refuse("STATE_SOURCE_MISMATCH")
    return path


def _file_identity(meta):
    # Windows creation/change timestamps differ between CRT fstat and lstat.
    return (meta.st_dev, meta.st_ino, meta.st_mode, meta.st_nlink, meta.st_size,
            meta.st_mtime_ns, getattr(meta, "st_birthtime_ns", None),
            getattr(meta, "st_file_attributes", None), getattr(meta, "st_reparse_tag", None))


def _directory_identity(meta):
    return (meta.st_dev, meta.st_ino, meta.st_mode,
            getattr(meta, "st_file_attributes", 0), getattr(meta, "st_reparse_tag", 0))


def _ordinary(meta, *, directory=False):
    valid_type = stat.S_ISDIR(meta.st_mode) if directory else stat.S_ISREG(meta.st_mode)
    if (not valid_type or stat.S_ISLNK(meta.st_mode)
            or getattr(meta, "st_file_attributes", 0) & _REPARSE
            or (not directory and meta.st_nlink != 1)):
        _refuse("STATE_SOURCE_MISMATCH")


def _win_open(path, *, directory=False):
    """Open the named object itself; never follow a Windows reparse point."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL

    class Information(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("creation", wintypes.FILETIME),
                    ("access", wintypes.FILETIME), ("write", wintypes.FILETIME),
                    ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD),
                    ("size_low", wintypes.DWORD), ("links", wintypes.DWORD),
                    ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD)]

    information = kernel.GetFileInformationByHandle
    information.argtypes = (wintypes.HANDLE, ctypes.POINTER(Information))
    information.restype = wintypes.BOOL
    access = 0x80 if directory else 0x80000000
    share = 3 if directory else 1  # In particular, do not grant delete sharing.
    flags = 0x200000 | (0x02000000 if directory else 0)
    handle = create(str(path), access, share, None, 3, flags, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    transferred = False
    try:
        info = Information()
        if not information(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if (info.attributes & _REPARSE or bool(info.attributes & 0x10) != directory
                or (not directory and info.links != 1)):
            _refuse("STATE_SOURCE_MISMATCH")
        if directory:
            transferred = True
            return handle, close
        import msvcrt
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        handle = None  # The CRT descriptor now owns the native handle.
        return descriptor, os.close
    finally:
        if handle is not None and not transferred:
            close(handle)


class _DirectoryRoute:
    """Hold every directory in an absolute, ordinary, no-follow route."""

    def __init__(self, path):
        self.path = _absolute(path)
        self.handles = []
        self.identities = []
        self.fd = None

    def __enter__(self):
        current = Path(self.path.anchor)
        try:
            for part in (None,) + self.path.parts[1:]:
                if part is not None:
                    current /= part
                before = os.lstat(current)
                _ordinary(before, directory=True)
                if os.name == "nt":
                    handle, close = _win_open(current, directory=True)
                else:
                    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                    handle = (os.open(current, flags) if self.fd is None
                              else os.open(part, flags, dir_fd=self.fd))
                    close = os.close
                    if _directory_identity(os.fstat(handle)) != _directory_identity(before):
                        os.close(handle)
                        _refuse("STATE_SOURCE_MISMATCH")
                    self.fd = handle
                self.handles.append((handle, close))
                after = os.lstat(current)
                if _directory_identity(before) != _directory_identity(after):
                    _refuse("STATE_SOURCE_MISMATCH")
                self.identities.append((current, _directory_identity(after)))
            self.verify()
            return self
        except (OSError, StateRefusal):
            self.__exit__(None, None, None)
            raise

    def verify(self):
        for path, identity in self.identities:
            meta = os.lstat(path)
            _ordinary(meta, directory=True)
            if _directory_identity(meta) != identity:
                _refuse("STATE_SOURCE_MISMATCH")

    def __exit__(self, exc_type, exc, traceback):
        handles, self.handles = self.handles, []
        close_error = None
        for handle, close in reversed(handles):
            try:
                # CloseHandle returns zero on failure; os.close returns None.
                if close(handle) == 0:
                    raise RuntimeError("STATE_DIRECTORY_CLOSE_FAILED")
            except BaseException as error:
                # Ownership is uncertain after a failed close; never retry it.
                if close_error is None:
                    close_error = error
        if close_error is not None and not isinstance(exc, RuntimeError):
            raise RuntimeError("STATE_DIRECTORY_CLOSE_FAILED") from close_error
        # Keep an existing cleanup/recovery RuntimeError and its chain intact.

    def open(self, name, flags):
        if os.name == "nt":
            return os.open(self.path / name, flags)
        return os.open(name, flags, dir_fd=self.fd)

    def replace(self, name):
        self.verify()
        if os.name == "nt":
            os.replace(self.path / name, self.path / _RECORD)
        else:
            os.replace(name, _RECORD, src_dir_fd=self.fd, dst_dir_fd=self.fd)

    def unlink(self, name):
        if os.name == "nt":
            os.unlink(self.path / name)
        else:
            os.unlink(name, dir_fd=self.fd)


def _read_regular(path):
    with _DirectoryRoute(path.parent) as route:
        before = os.lstat(path)
        _ordinary(before)
        if os.name == "nt":
            descriptor, close = _win_open(path)
        else:
            descriptor = route.open(path.name, os.O_RDONLY | os.O_NOFOLLOW)
            close = os.close
        try:
            opened = os.fstat(descriptor)
            _ordinary(opened)
            if _file_identity(opened) != _file_identity(before):
                _refuse("STATE_SOURCE_MISMATCH")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(before.st_size + 1)
            final_opened = os.fstat(descriptor)
            after = os.lstat(path)
            if (len(raw) != before.st_size or _file_identity(opened) != _file_identity(final_opened)
                    or opened.st_ctime_ns != final_opened.st_ctime_ns
                    or _file_identity(before) != _file_identity(after)
                    or before.st_ctime_ns != after.st_ctime_ns):
                _refuse("STATE_SOURCE_MISMATCH")
            route.verify()
            return raw
        finally:
            close(descriptor)


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            _refuse("STATE_JSON_INVALID")
        value[key] = item
    return value


def _constant(value):
    _refuse("STATE_JSON_INVALID")


def _json(raw):
    try:
        return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_pairs,
                          parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, StateRefusal):
            raise
        raise StateRefusal("STATE_JSON_INVALID") from None


def _canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8", "strict") + b"\n"
    except (UnicodeError, ValueError, RecursionError):
        raise StateRefusal("STATE_VALUE_INVALID") from None


def _string(value):
    if type(value) is not str:
        _refuse("STATE_VALUE_INVALID")
    try:
        value.encode("utf-8", "strict")
    except UnicodeError:
        raise StateRefusal("STATE_VALUE_INVALID") from None


def _logical(value):
    _string(value)
    parts = value.split("/")
    if (len(parts) < 2 or any(part in ("", ".", "..") for part in parts)
            or "\\" in value or ":" in value or any(ord(char) < 32 for char in value)
            or PurePosixPath(value).as_posix() != value):
        _refuse("STATE_VALUE_INVALID")


def _number(value):
    if type(value) not in (int, float):
        _refuse("STATE_VALUE_INVALID")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        _refuse("STATE_VALUE_INVALID")


def _node(value, node, depth=0):
    if depth > 64:
        _refuse("STATE_VALUE_INVALID")
    kind = node["kind"]
    if kind == "object":
        fields = node["fields"]
        if type(value) is not dict or set(value) != {field["name"] for field in fields}:
            _refuse("STATE_FIELDS_INVALID")
        for field in fields:
            item = value[field["name"]]
            if item is None and field["nullable"]:
                continue
            _node(item, field["node"], depth + 1)
    elif kind == "list":
        if type(value) is not list:
            _refuse("STATE_VALUE_INVALID")
        for item in value:
            _node(item, node["item"], depth + 1)
    elif kind == "integer":
        if type(value) is not int:
            _refuse("STATE_INTEGER_REQUIRED")
    elif kind == "number":
        _number(value)
    elif kind == "string":
        _string(value)
    elif kind == "logical-ref":
        _logical(value)
    elif kind == "sha256":
        _string(value)
        if not _SHA.fullmatch(value):
            _refuse("STATE_VALUE_INVALID")
    else:
        _refuse("STATE_SOURCE_MISMATCH")


def _schema(host, asset_version):
    if type(host) is not str or host != _HOST:
        _refuse("STATE_HOST_MISMATCH")
    if type(asset_version) is not str or asset_version != "1.0.0":
        _refuse("STATE_VERSION_MISMATCH")
    module_path = _absolute(Path(__file__))
    if module_path.parts[-5:] != ("client-bundle", "shared-assets", _HOST, _OWNER, "state_io.py"):
        _refuse("STATE_SOURCE_MISMATCH")
    raw = _read_regular(module_path.with_name("state-schema.json"))
    if hashlib.sha256(raw).hexdigest() != _SCHEMA_SHA:
        _refuse("STATE_SOURCE_MISMATCH")
    schema = _json(raw)
    keys = {"asset_version", "content_sha256", "host", "logical_ref", "owner",
            "schema_format", "schema_version", "state_definition"}
    if (type(schema) is not dict or set(schema) != keys or schema["host"] != _HOST
            or schema["owner"] != _OWNER or schema["asset_version"] != asset_version
            or type(schema["schema_version"]) is not int or schema["schema_version"] != 1
            or schema["schema_format"] != "lhx-state-v1"
            or schema["content_sha256"] != _DEFINITION_SHA
            or schema["logical_ref"] != _REPOSITORY + "/client-bundle/shared-assets/" + _HOST + "/" + _OWNER + "/state-schema.json"):
        _refuse("STATE_SOURCE_MISMATCH")
    if _read_regular(module_path.parents[2] / "version.json") != _VERSION_RAW:
        _refuse("STATE_VERSION_MISMATCH")
    return schema["state_definition"]


def _nonempty(value):
    if not value or not value.strip() or any(ord(char) < 32 for char in value):
        _refuse("STATE_VALUE_INVALID")


def _bootstrap_raw_sha(raw):
    actual_sha = hashlib.sha256(raw).hexdigest()
    if (actual_sha, len(raw)) not in _BOOTSTRAP_RAW_IDENTITIES:
        _refuse("SOURCE_BYTES_CHANGED")
    return actual_sha


def _domain(record):
    if record["schema_version"] != 1:
        _refuse("STATE_VALUE_INVALID")
    if record["host"] != _HOST:
        _refuse("STATE_HOST_MISMATCH")
    if record["asset_version"] != "1.0.0":
        _refuse("STATE_VERSION_MISMATCH")
    if record["generation"] < 0 or record["delivery_count"] < 0:
        _refuse("STATE_VALUE_INVALID")
    if record["bootstrap_ref"] != _BOOTSTRAP_REF:
        _refuse("STATE_SOURCE_MISMATCH")
    for field in ("session_id", "last_event_id"):
        _nonempty(record[field])
    sessions = record["delivered_sessions"]
    if not sessions or len(sessions) != len(set(sessions)) or record["delivery_count"] != len(sessions):
        _refuse("STATE_VALUE_INVALID")
    for session in sessions:
        _nonempty(session)
    if sessions[-1] != record["session_id"]:
        _refuse("STATE_VALUE_INVALID")
    bootstrap = Path(__file__).parents[4] / "skills" / "using-superpowers" / "SKILL.md"
    actual_raw = _read_regular(bootstrap)
    actual_sha = _bootstrap_raw_sha(actual_raw)
    try:
        actual_raw.decode("utf-8", "strict")
    except UnicodeError:
        raise StateRefusal("STATE_SOURCE_MISMATCH") from None
    if (record["bootstrap_raw_sha256"] != actual_sha
            or record["delivered_context_sha256"] != actual_sha):
        _refuse("STATE_SOURCE_MISMATCH")


def _validate(record, definition):
    _node(record, definition)
    _domain(record)


def read_state(state_root: Path, *, host: str, asset_version: str) -> dict:
    """Read only the selected record and refuse missing, corrupt or unsafe input."""
    try:
        definition = _schema(host, asset_version)
        root = _absolute(state_root)
        with _DirectoryRoute(root):
            record = _json(_read_regular(root / _RECORD))
            _validate(record, definition)
            return record
    except OSError:
        raise StateRefusal("STATE_SOURCE_MISMATCH") from None


def _remove_temporary(route, name):
    try:
        if os.name == "nt":
            os.lstat(route.path / name)
        else:
            os.stat(name, dir_fd=route.fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError:
        raise RuntimeError("STATE_TEMP_CLEANUP_FAILED") from None
    try:
        route.unlink(name)
    except OSError:
        raise RuntimeError("STATE_TEMP_CLEANUP_FAILED") from None


def _temporary(route, raw):
    name = "." + _RECORD + "." + uuid.uuid4().hex + ".tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = route.open(name, flags)
    try:
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(descriptor)
        finally:
            try:
                os.close(descriptor)
            except OSError:
                # A failed close leaves descriptor ownership uncertain; never retry it.
                raise RuntimeError("STATE_TEMP_CLOSE_FAILED") from None
    except BaseException:
        _remove_temporary(route, name)
        raise
    return name


def _restore(route, old_raw):
    if old_raw is None:
        route.unlink(_RECORD)
    else:
        name = _temporary(route, old_raw)
        try:
            route.replace(name)
        finally:
            _remove_temporary(route, name)


def write_state(state_root: Path, record: dict, *, host: str, asset_version: str) -> bytes:
    """Validate before writing; return complete, independently read persisted bytes."""
    try:
        definition = _schema(host, asset_version)
        _validate(record, definition)
        raw = _canonical(record)
        root = _absolute(state_root)
        with _DirectoryRoute(root) as route:
            try:
                old_raw = _read_regular(root / _RECORD)
            except FileNotFoundError:
                old_raw = None
            name = _temporary(route, raw)
            replaced = False
            try:
                if _read_regular(root / name) != raw:
                    _refuse("STATE_SOURCE_MISMATCH")
                if old_raw is None:
                    if os.path.lexists(root / _RECORD):
                        _refuse("STATE_SOURCE_MISMATCH")
                elif _read_regular(root / _RECORD) != old_raw:
                    _refuse("STATE_SOURCE_MISMATCH")
                route.replace(name)
                replaced = True
                readback = read_state(root, host=host, asset_version=asset_version)
                actual_raw = _read_regular(root / _RECORD)
                if actual_raw != _canonical(readback) or actual_raw != raw:
                    _refuse("STATE_SOURCE_MISMATCH")
                return actual_raw
            except (OSError, StateRefusal):
                if replaced:
                    try:
                        _restore(route, old_raw)
                    except (OSError, StateRefusal):
                        raise RuntimeError("STATE_RESTORE_FAILED") from None
                raise
            finally:
                _remove_temporary(route, name)
    except OSError:
        raise StateRefusal("STATE_SOURCE_MISMATCH") from None
