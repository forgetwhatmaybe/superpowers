"""Actual bounded functional captures, UNOBSERVED and not OwnerEvidence."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import os
import stat
from pathlib import Path

from . import state_io as _state
from .source_interface import (handle_event, _canonical, _json, _diagnostic_binding,
                               _disposition, _source_root)
from .state_io import StateRefusal, read_state, write_state

_HOST, _OWNER, _REPOSITORY = _state._HOST, _state._OWNER, _state._REPOSITORY
_PURPOSES = frozenset(("state-roundtrip", "state-refusal", "interface-success",
                       "interface-failure", "no-credential-read"))


def _separate(first, second):
    if first == second or first in second.parents or second in first.parents:
        raise ValueError("UNVERIFIED_EVIDENCE_BINDING")


def _capture_binding(purpose, case_id, state_root, source_roots, evidence_root, host, asset_version):
    if type(purpose) is not str or purpose not in _PURPOSES or type(case_id) is not str:
        raise ValueError("UNVERIFIED_CASE_BINDING")
    if case_id != _REPOSITORY + ":" + _HOST + ":" + purpose:
        raise ValueError("UNVERIFIED_CASE_BINDING")
    if host != _HOST or asset_version != "1.0.0":
        raise ValueError("UNVERIFIED_CASE_BINDING")
    source_root = _source_root(source_roots)
    for path in (state_root, evidence_root):
        if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
            raise ValueError("UNVERIFIED_EVIDENCE_BINDING")
    _separate(evidence_root, state_root)
    _separate(evidence_root, source_root)
    _separate(state_root, source_root)
    diagnostic_ref = "/".join((_REPOSITORY, "actual", _HOST, purpose, "diagnostic.txt"))
    _diagnostic_binding(diagnostic_ref)
    return diagnostic_ref, source_root


def _physical_separation(routes):
    # Every identity belongs to an ordinary, no-follow directory whose handle
    # is still held by _DirectoryRoute. Compare roots against every held route
    # component, so alternate Windows spellings cannot hide containment.
    for route in routes:
        route.verify()
    roots = [route.identities[-1][1][:2] for route in routes]
    for index, root in enumerate(roots):
        for other_index, route in enumerate(routes):
            if index != other_index and any(root == identity[:2]
                    for path, identity in route.identities):
                raise ValueError("UNVERIFIED_EVIDENCE_BINDING")


def _state_members(state_route):
    # Only the fixed selected record body is read. Unknown private members are
    # compared by no-follow metadata, including nested membership, without
    # opening their bodies or following private reparse points.
    members = {}
    with ExitStack() as stack:
        pending = [("", state_route)]
        while pending:
            prefix, route = pending.pop()
            route.verify()
            with os.scandir(route.path) as entries:
                for entry in entries:
                    name = prefix + entry.name
                    meta = os.lstat(route.path / entry.name)
                    if not prefix and entry.name == _state._RECORD:
                        continue
                    members[name] = (_state._file_identity(meta), meta.st_ctime_ns)
                    if (stat.S_ISDIR(meta.st_mode) and not stat.S_ISLNK(meta.st_mode)
                            and not getattr(meta, "st_file_attributes", 0) & _state._REPARSE):
                        child = stack.enter_context(_state._DirectoryRoute(route.path / entry.name))
                        pending.append((name + "/", child))
            route.verify()
        try:
            selected_raw = _state._read_regular(state_route.path / _state._RECORD)
        except FileNotFoundError:
            selected_raw = None
        state_route.verify()
    return selected_raw, members


def _unchanged_refusal(state_route, before):
    if _state_members(state_route) != before:
        raise RuntimeError("UNVERIFIED_REFUSAL_STATE_CHANGED")


def _new_capture_route(stack, evidence_root, slug):
    route = stack.enter_context(_state._DirectoryRoute(evidence_root))
    for part in (_REPOSITORY, "actual", _HOST, slug):
        child = route.path / part
        try:
            meta = os.lstat(child)
        except FileNotFoundError:
            if os.name == "nt":
                os.mkdir(child)
            else:
                os.mkdir(part, dir_fd=route.fd)
            meta = os.lstat(child)
        _state._ordinary(meta, directory=True)
        route.verify()
        route = stack.enter_context(_state._DirectoryRoute(child))
    if tuple(route.path.iterdir()):
        raise ValueError("UNVERIFIED_EVIDENCE_BINDING")
    return route


def _write_evidence(route, name, raw):
    if type(raw) is not bytes or name not in {"state.json", "readback.json", "interface.json",
                                             "stdout.bin", "stderr.bin", "diagnostic.txt"}:
        raise RuntimeError("UNVERIFIED_CAPTURE_BYTES")
    route.verify()
    descriptor = route.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        _state._ordinary(os.fstat(descriptor))
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            count = stream.write(raw)
            if count != len(raw):
                raise RuntimeError("UNVERIFIED_CAPTURE_BYTES")
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if _state._read_regular(route.path / name) != raw:
        raise RuntimeError("UNVERIFIED_CAPTURE_BYTES")
    route.verify()


def run_case(purpose: str, input_bytes: bytes, *, state_root: Path, source_roots: Mapping[str, Path],
             evidence_root: Path, host: str, asset_version: str, case_id: str) -> dict:
    """Call genuine Source functions; no expected path or expected value argument."""
    diagnostic_ref, source_root = _capture_binding(purpose, case_id, state_root,
        source_roots, evidence_root, host, asset_version)
    output, error = io.StringIO(), io.StringIO()
    interface, state_raw, readback_raw, rejection = None, None, None, None
    with ExitStack() as stack:
        state_route = stack.enter_context(_state._DirectoryRoute(state_root))
        source_route = stack.enter_context(_state._DirectoryRoute(source_root))
        evidence_route = stack.enter_context(_state._DirectoryRoute(evidence_root))
        _physical_separation((state_route, source_route, evidence_route))
        route = _new_capture_route(stack, evidence_root, purpose)
        with redirect_stdout(output), redirect_stderr(error):
            if purpose in ("state-roundtrip", "state-refusal"):
                record = _json(input_bytes, "STATE_JSON_INVALID")
                before_refusal = _state_members(state_route)
                try:
                    state_raw = write_state(state_root, record, host=host, asset_version=asset_version)
                    readback_raw = _canonical(read_state(state_root, host=host, asset_version=asset_version))
                except StateRefusal as refusal:
                    if state_raw is not None:
                        raise RuntimeError("UNVERIFIED_STATE_READBACK") from refusal
                    _unchanged_refusal(state_route, before_refusal)
                    category, stage = _disposition(refusal.reason_code)
                    diagnostic_raw = (refusal.reason_code + "\n").encode("utf-8")
                    error.write(diagnostic_raw.decode("utf-8"))
                    rejection = {"category": category, "reason_code": refusal.reason_code,
                        "stage": stage, "diagnostic": {"evidence_ref": diagnostic_ref,
                        "raw_sha256": hashlib.sha256(diagnostic_raw).hexdigest()}}
            else:
                request = _json(input_bytes)
                if (type(request) is not dict or set(request) != {"setup", "event"}
                        or type(request["setup"]) is not dict
                        or set(request["setup"]) != {"initial_state"}):
                    raise ValueError("UNVERIFIED_CASE_INPUT")
                write_state(state_root, request["setup"]["initial_state"], host=host, asset_version=asset_version)
                read_state(state_root, host=host, asset_version=asset_version)
                before_refusal = _state_members(state_route)
                interface = handle_event(_canonical(request["event"]), state_root=state_root,
                    source_roots=source_roots, host=host, asset_version=asset_version,
                    diagnostic_ref=diagnostic_ref)
                if type(interface) is not dict or set(interface) != {"schema_version", "repository", "owner",
                    "host", "status", "operation", "data", "rejection"}:
                    raise RuntimeError("UNVERIFIED_INTERFACE_OUTPUT")
                if interface["status"] == "ok":
                    if interface["rejection"] is not None or interface["data"] is None:
                        raise RuntimeError("UNVERIFIED_INTERFACE_OUTPUT")
                    state_raw = _state._read_regular(state_root / _state._RECORD)
                    readback_raw = _canonical(read_state(state_root, host=host, asset_version=asset_version))
                elif interface["status"] == "rejected":
                    if interface["data"] is not None or type(interface["rejection"]) is not dict:
                        raise RuntimeError("UNVERIFIED_INTERFACE_OUTPUT")
                    _unchanged_refusal(state_route, before_refusal)
                    rejection = interface["rejection"]
                else:
                    raise RuntimeError("UNVERIFIED_INTERFACE_OUTPUT")
        stdout_raw = output.getvalue().encode("utf-8")
        stderr_raw = error.getvalue().encode("utf-8")
        if stdout_raw:
            raise RuntimeError("UNVERIFIED_CAPTURE_STDOUT")
        if rejection is not None:
            reason = rejection["reason_code"]
            category, stage = _disposition(reason)
            diagnostic = {"evidence_ref": diagnostic_ref,
                          "raw_sha256": hashlib.sha256(stderr_raw).hexdigest()}
            if (set(rejection) != {"category", "reason_code", "stage", "diagnostic"}
                    or rejection["category"] != category or rejection["stage"] != stage
                    or rejection["diagnostic"] != diagnostic
                    or stderr_raw != (reason + "\n").encode("utf-8")
                    or state_raw is not None or readback_raw is not None):
                raise RuntimeError("UNVERIFIED_CAPTURE_DIAGNOSTIC")
            _write_evidence(route, "diagnostic.txt", stderr_raw)
        elif stderr_raw:
            raise RuntimeError("UNVERIFIED_CAPTURE_STDERR")
        if state_raw is not None:
            if state_raw != readback_raw:
                raise RuntimeError("UNVERIFIED_STATE_READBACK")
            _write_evidence(route, "state.json", state_raw)
            _write_evidence(route, "readback.json", readback_raw)
        if interface is not None:
            _write_evidence(route, "interface.json", _canonical(interface))
        _write_evidence(route, "stdout.bin", stdout_raw)
        _write_evidence(route, "stderr.bin", stderr_raw)
    return {"observation_status": "UNOBSERVED", "case_id": case_id,
            "exit_code": 2 if rejection is not None else 0,
            "actual_evidence_ref": "/".join((_REPOSITORY, "actual", _HOST, purpose)),
            "interface": interface, "rejection": rejection}
