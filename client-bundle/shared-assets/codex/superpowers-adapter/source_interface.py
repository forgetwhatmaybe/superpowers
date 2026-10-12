"""Closed owned Source interface; functional result, no native binding claim."""
from __future__ import annotations

from collections.abc import Mapping
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import sys
import types

from . import state_io as _state
from .state_io import StateRefusal, read_state, write_state

_HOST, _OWNER, _REPOSITORY = _state._HOST, _state._OWNER, _state._REPOSITORY
_COMMON_FIELDS = {"schema_version", "host", "operation", "event", "session_id", "event_id", "observed_at"}
_POLICY_REASONS = frozenset(("SOURCE_BYTES_CHANGED", "NATIVE_EXECUTION_UNVERIFIED",
                            "PRODUCER_BINDING_UNKNOWN", "CRAP_SCORE_BLOCKED"))


def _refuse(reason):
    raise StateRefusal(reason)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8", "strict") + b"\n"


def _json(raw, reason="INTERFACE_JSON_INVALID"):
    if type(raw) is not bytes:
        _refuse(reason)
    try:
        text = raw.decode("utf-8", "strict")
        depth, quoted, escaped = 0, False, False
        for character in text:
            if quoted:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    quoted = False
            elif character == '"':
                quoted = True
            elif character in "[{":
                depth += 1
                if depth > 64:
                    _refuse(reason)
            elif character in "]}":
                depth -= 1

        def pairs(items):
            value = {}
            for key, item in items:
                if key in value:
                    _refuse(reason)
                value[key] = item
            return value

        def constant(value):
            _refuse(reason)

        def floating(value):
            number = float(value)
            if not math.isfinite(number):
                _refuse(reason)
            return number

        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant,
                           parse_float=floating)
        _canonical(value)
        return value
    except (UnicodeError, ValueError, RecursionError, OverflowError):
        raise StateRefusal(reason) from None


def _text(value):
    if type(value) is not str or not value or not value.strip():
        _refuse("INTERFACE_FIELDS_INVALID")
    try:
        value.encode("utf-8", "strict")
    except UnicodeError:
        raise StateRefusal("INTERFACE_FIELDS_INVALID") from None


def _integer(value):
    if type(value) is not int or value < 0:
        _refuse("INTERFACE_FIELDS_INVALID")


def _number(value):
    if type(value) not in (int, float):
        _refuse("INTERFACE_FIELDS_INVALID")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        _refuse("INTERFACE_FIELDS_INVALID")


def _logical_parts(reference):
    if type(reference) is not str:
        _refuse("SOURCE_REFERENCE_INVALID")
    parts = reference.split("/")
    if (len(parts) < 2 or parts[0] != _REPOSITORY
            or any(part in ("", ".", "..") for part in parts)
            or "\\" in reference or ":" in reference
            or any(ord(char) < 32 or ord(char) == 127 for char in reference)
            or PurePosixPath(reference).as_posix() != reference):
        _refuse("SOURCE_REFERENCE_INVALID")
    return parts[1:]


def _diagnostic_binding(reference):
    if type(reference) is not str:
        raise ValueError("UNVERIFIED_DIAGNOSTIC_BINDING")
    parts = reference.split("/")
    if (len(parts) != 5 or parts[:3] != [_REPOSITORY, "actual", _HOST]
            or parts[-1] != "diagnostic.txt" or parts[3] in ("", ".", "..")
            or "\\" in reference or ":" in reference
            or any(ord(char) < 32 or ord(char) == 127 for char in reference)
            or PurePosixPath(reference).as_posix() != reference):
        raise ValueError("UNVERIFIED_DIAGNOSTIC_BINDING")
    try:
        reference.encode("utf-8", "strict")
    except UnicodeError:
        raise ValueError("UNVERIFIED_DIAGNOSTIC_BINDING") from None
    return reference


def _disposition(reason):
    if reason not in _state._REASONS:
        raise RuntimeError("UNVERIFIED_REFUSAL_REASON")
    if reason.startswith("STATE_"):
        return "invalid-state", "state-validation"
    if reason in _POLICY_REASONS:
        return "controlled-policy-rejection", "controlled-policy"
    return "invalid-interface-input", "interface-validation"


def _rejection(reason, operation, diagnostic_ref):
    category, stage = _disposition(reason)
    raw = (reason + "\n").encode("utf-8")
    sys.stderr.write(raw.decode("utf-8"))
    return {"schema_version": 1, "repository": _REPOSITORY, "owner": _OWNER,
            "host": _HOST, "status": "rejected", "operation": operation,
            "data": None, "rejection": {"category": category, "reason_code": reason,
            "stage": stage, "diagnostic": {"evidence_ref": diagnostic_ref,
            "raw_sha256": hashlib.sha256(raw).hexdigest()}}}


def _success(operation, data):
    return {"schema_version": 1, "repository": _REPOSITORY, "owner": _OWNER,
            "host": _HOST, "status": "ok", "operation": operation,
            "data": data, "rejection": None}


def _validate_event(value, host, asset_version):
    if type(host) is not str or host != _HOST:
        _refuse("INTERFACE_HOST_MISMATCH")
    if type(asset_version) is not str or asset_version != "1.0.0":
        _refuse("STATE_VERSION_MISMATCH")
    if (type(value) is not dict or set(value) != _COMMON_FIELDS | _EXTRA_FIELDS
            or type(value["schema_version"]) is not int or value["schema_version"] != 1):
        _refuse("INTERFACE_FIELDS_INVALID")
    for key in ("host", "operation", "event", "session_id", "event_id", "observed_at"):
        _text(value[key])
    if value["host"] != host:
        _refuse("INTERFACE_HOST_MISMATCH")
    if value["event"] not in _EVENTS[_HOST]:
        _refuse("INTERFACE_EVENT_UNSUPPORTED")
    if value["operation"] not in ("source_event", "require_native_execution"):
        _refuse("INTERFACE_FIELDS_INVALID")
    _validate_specific(value)


def _source_root(source_roots):
    if (not isinstance(source_roots, Mapping) or set(source_roots) != {_REPOSITORY}
            or not isinstance(source_roots[_REPOSITORY], Path)):
        _refuse("SOURCE_REFERENCE_INVALID")
    root = source_roots[_REPOSITORY]
    if not root.is_absolute() or ".." in root.parts:
        _refuse("SOURCE_REFERENCE_INVALID")
    package = root / "client-bundle" / "shared-assets" / _HOST / _OWNER
    if (Path(__file__) != package / "source_interface.py"
            or Path(_state.__file__) != package / "state_io.py"):
        _refuse("SOURCE_REFERENCE_INVALID")
    return root


def _source_file(root, reference):
    path = root.joinpath(*_logical_parts(reference))
    try:
        with _state._DirectoryRoute(path.parent) as route:
            _state._ordinary(os.lstat(path))
            route.verify()
    except OSError:
        raise StateRefusal("SOURCE_REFERENCE_INVALID") from None
    return path


def _persist(state_root, record, host, asset_version):
    actual = write_state(state_root, record, host=host, asset_version=asset_version)
    readback = _committed_readback(state_root, actual, record, host, asset_version)
    return readback


def _committed_readback(state_root, actual_raw, expected, host, asset_version):
    # The complete writer has already committed and returned. A later refusal
    # cannot describe the call as a controlled rejection with unchanged state.
    try:
        readback = read_state(state_root, host=host, asset_version=asset_version)
        if _canonical(readback) != actual_raw or readback != expected:
            raise RuntimeError("UNVERIFIED_STATE_READBACK")
        return readback
    except StateRefusal as error:
        raise RuntimeError("UNVERIFIED_STATE_READBACK") from error


def handle_event(input_bytes: bytes, *, state_root: Path, source_roots: Mapping[str, Path],
                 host: str, asset_version: str, diagnostic_ref: str) -> dict:
    """Execute actual owning transition; do not manufacture native acceptance."""
    diagnostic_ref = _diagnostic_binding(diagnostic_ref)
    operation = "source_event"
    try:
        value = _json(input_bytes)
        if type(value) is dict and value.get("operation") in ("source_event", "require_native_execution"):
            operation = value["operation"]
        _validate_event(value, host, asset_version)
        source_root = _source_root(source_roots)
        with _state._DirectoryRoute(source_root):
            if operation == "require_native_execution":
                _refuse("NATIVE_EXECUTION_UNVERIFIED")
            return _success(operation, _transition(value, state_root, source_root,
                                                   host, asset_version))
    except StateRefusal as error:
        return _rejection(error.reason_code, operation, diagnostic_ref)


_EXTRA_FIELDS = {"bootstrap_ref"}
_EVENTS = {"pi": frozenset(("before_agent_start",)), "codex": frozenset(("SessionStart",))}
_BOOTSTRAP_REF = "superpowers/skills/using-superpowers/SKILL.md"


def _validate_specific(value):
    _text(value["bootstrap_ref"])
    _logical_parts(value["bootstrap_ref"])
    if value["bootstrap_ref"] != _BOOTSTRAP_REF:
        _refuse("SOURCE_REFERENCE_INVALID")


def _transition(value, state_root, source_root, host, asset_version):
    path = _source_file(source_root, value["bootstrap_ref"])
    raw = _state._read_regular(path)
    actual_sha = _state._bootstrap_raw_sha(raw)
    try:
        context = raw.decode("utf-8", "strict")
    except UnicodeError:
        raise StateRefusal("SOURCE_BYTES_CHANGED") from None
    previous = read_state(state_root, host=host, asset_version=asset_version)
    repeat = value["session_id"] in previous["delivered_sessions"]
    if repeat:
        readback = previous
    else:
        record = copy.deepcopy(previous)
        record["generation"] += 1
        record["session_id"], record["last_event_id"] = value["session_id"], value["event_id"]
        record["delivered_sessions"].append(value["session_id"])
        record["delivery_count"] = len(record["delivered_sessions"])
        record["bootstrap_ref"], record["bootstrap_raw_sha256"] = _BOOTSTRAP_REF, actual_sha
        record["delivered_context_sha256"] = actual_sha
        readback = _persist(state_root, record, host, asset_version)
    return {"bootstrap_ref": _BOOTSTRAP_REF, "bootstrap_raw_sha256": actual_sha,
            "delivery": "already-delivered" if repeat else "new",
            "additional_context": "" if repeat else context,
            "delivery_count": readback["delivery_count"], "native_injection_verified": False}
