# a51-ws: save and restore named iTerm2 workspaces.
# Copyright (C) 2026 Area 51 Software
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
"""Saved-workspace files: where they live, which names are allowed, and what a valid file looks like.

Nothing here talks to iTerm2, so all of it can be tested without iTerm2 running.
A saved file is hand-editable, so everything read from disk is validated before it is used.
"""
import json
import os
import re
import tempfile
from pathlib import Path

SAVED_FORMAT_VERSION = 1
MAXIMUM_SPLIT_DEPTH = 20
MAXIMUM_TAB_TITLE_LENGTH = 200
VALID_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class WorkspaceError(Exception):
    """A problem the person can fix (bad name, missing or damaged file). Shown without a traceback."""


def workspaces_folder():
    override = os.environ.get("A51_WS_FOLDER")
    return Path(override).expanduser() if override else Path.home() / ".config" / "a51-ws"


def check_workspace_name(name):
    """Names become file names, so only letters, digits, dot, dash and underscore are allowed."""
    if not VALID_NAME_PATTERN.match(name):
        raise WorkspaceError(
            f"'{name}' is not a usable workspace name. Use 1-64 letters, digits, '.', '-' or '_', "
            "starting with a letter or digit.")
    return name


def workspace_file(name):
    return workspaces_folder() / f"{check_workspace_name(name)}.json"


# ---------------------------------------------------------------- validation

def check_pane(node, where):
    folder = node.get("folder")
    if folder is not None and not isinstance(folder, str):
        raise WorkspaceError(f"{where}: 'folder' must be text.")
    if not isinstance(node.get("runs_claude", False), bool):
        raise WorkspaceError(f"{where}: 'runs_claude' must be true or false.")
    if not isinstance(node.get("appearance", {}), dict):
        raise WorkspaceError(f"{where}: 'appearance' must be an object.")


def check_layout(node, where, depth=0):
    if not isinstance(node, dict):
        raise WorkspaceError(f"{where}: expected an object with a 'type'.")
    if depth > MAXIMUM_SPLIT_DEPTH:
        raise WorkspaceError(f"{where}: splits are nested more than {MAXIMUM_SPLIT_DEPTH} deep.")
    node_type = node.get("type")
    if node_type == "pane":
        check_pane(node, where)
    elif node_type == "split":
        if not isinstance(node.get("side_by_side", False), bool):
            raise WorkspaceError(f"{where}: 'side_by_side' must be true or false.")
        children = node.get("children")
        if not isinstance(children, list) or not children:
            raise WorkspaceError(f"{where}: a split needs a non-empty 'children' list.")
        for child_number, child in enumerate(children, 1):
            check_layout(child, f"{where} > child {child_number}", depth + 1)
    else:
        raise WorkspaceError(f"{where}: 'type' must be 'pane' or 'split', found {node_type!r}.")


def check_tab_title(tab, where):
    title = tab.get("tab_title")
    if title is None:
        return
    if not isinstance(title, str):
        raise WorkspaceError(f"{where}: 'tab_title' must be text.")
    if len(title) > MAXIMUM_TAB_TITLE_LENGTH:
        raise WorkspaceError(f"{where}: 'tab_title' is too long (over {MAXIMUM_TAB_TITLE_LENGTH} characters).")


def check_frame(frame, where):
    is_four_numbers = (isinstance(frame, list) and len(frame) == 4
                       and all(isinstance(value, (int, float)) and not isinstance(value, bool)
                               for value in frame))
    if not is_four_numbers:
        raise WorkspaceError(f"{where}: 'frame' must be four numbers [x, y, width, height].")


def check_workspace(saved, name="workspace"):
    """Raise WorkspaceError, naming the exact spot, unless `saved` is a complete valid workspace."""
    if not isinstance(saved, dict):
        raise WorkspaceError(f"'{name}': the file must hold a JSON object.")
    format_version = saved.get("format_version", SAVED_FORMAT_VERSION)
    if not isinstance(format_version, int) or format_version > SAVED_FORMAT_VERSION:
        raise WorkspaceError(
            f"'{name}' was saved by a newer a51-ws (format {format_version}). Please upgrade a51-ws.")
    windows = saved.get("windows")
    if not isinstance(windows, list) or not windows:
        raise WorkspaceError(f"'{name}': needs a non-empty 'windows' list.")
    for window_number, window in enumerate(windows, 1):
        where = f"'{name}' window {window_number}"
        if not isinstance(window, dict):
            raise WorkspaceError(f"{where}: expected an object.")
        if "frame" in window:
            check_frame(window["frame"], where)
        tabs = window.get("tabs")
        if not isinstance(tabs, list) or not tabs:
            raise WorkspaceError(f"{where}: needs a non-empty 'tabs' list.")
        for tab_number, tab in enumerate(tabs, 1):
            check_layout(tab, f"{where} tab {tab_number}")
            check_tab_title(tab, f"{where} tab {tab_number}")
    return saved


# ---------------------------------------------------------------- exact-case names

def lookup_workspace(name):
    """Is there a saved workspace called exactly `name`?

    Returns ("exact", name), ("different_case", stored_name) or ("missing", None).
    a51-ws names are case-sensitive, but the default macOS disk is not, so 'Work' and 'work' would
    silently be the same file. Checking the real file names (not asking the disk) keeps them apart.
    """
    check_workspace_name(name)
    folder = workspaces_folder()
    stored_names = [path.stem for path in folder.glob("*.json")] if folder.is_dir() else []
    if name in stored_names:
        return "exact", name
    for stored_name in sorted(stored_names):
        if stored_name.lower() == name.lower():
            return "different_case", stored_name
    return "missing", None


def refuse_different_case(name, stored_name):
    raise WorkspaceError(
        f"'{name}' differs only by capital letters from '{stored_name}'. Workspace names are "
        "case-sensitive, but they are stored as files and a Mac treats those as the same file. "
        "Pick a different name.")


# ---------------------------------------------------------------- reading and writing

def load_workspace(name):
    path = workspace_file(name)
    kind, stored_name = lookup_workspace(name)
    if kind == "different_case":
        raise WorkspaceError(
            f"No saved workspace called '{name}'. Did you mean '{stored_name}'? (Names are case-sensitive.)")
    try:
        text = path.read_text()
    except FileNotFoundError:
        raise WorkspaceError(f"No saved workspace called '{name}'. Try: a51-ws list") from None
    except OSError as error:
        raise WorkspaceError(f"Could not read {path}: {error.strerror or error}") from None
    try:
        saved = json.loads(text)
    except json.JSONDecodeError as error:
        raise WorkspaceError(
            f"{path} is not valid JSON ({error.msg}, line {error.lineno}). "
            "Fix it by hand, or delete it and save again.") from None
    return check_workspace(saved, name)


def save_workspace_file(name, windows):
    """Write atomically: a crash or full disk can never leave a half-written workspace behind."""
    path = workspace_file(name)
    kind, stored_name = lookup_workspace(name)
    if kind == "different_case":
        refuse_different_case(name, stored_name)
    existed = kind == "exact"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
                "w", dir=path.parent, prefix=f".{name}.", suffix=".tmp", delete=False) as temporary:
            json.dump({"format_version": SAVED_FORMAT_VERSION, "windows": windows}, temporary, indent=2)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary.name, path)
    except OSError as error:
        raise WorkspaceError(f"Could not save to {path}: {error.strerror or error}") from None
    return path, existed


def remove_workspace_file(name):
    """Return True if a file was removed, False if there was nothing to remove."""
    path = workspace_file(name)
    kind, stored_name = lookup_workspace(name)
    if kind == "different_case":
        raise WorkspaceError(
            f"No saved workspace called '{name}'. Did you mean '{stored_name}'? (Names are case-sensitive.)")
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise WorkspaceError(f"Could not remove {path}: {error.strerror or error}") from None
    return True


def list_workspace_summaries():
    """(name, tab_count) per saved workspace; tab_count is None when the file is damaged."""
    folder = workspaces_folder()
    summaries = []
    for path in sorted(folder.glob("*.json")) if folder.exists() else []:
        if not VALID_NAME_PATTERN.match(path.stem):
            continue
        try:
            saved = load_workspace(path.stem)
            summaries.append((path.stem, sum(len(window["tabs"]) for window in saved["windows"])))
        except WorkspaceError:
            summaries.append((path.stem, None))
    return summaries


# ---------------------------------------------------------------- reading a layout

def count_panes(node):
    if node["type"] == "pane":
        return 1
    return sum(count_panes(child) for child in node["children"])


def first_pane(node):
    return node if node["type"] == "pane" else first_pane(node["children"][0])
