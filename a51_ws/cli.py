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
"""a51-ws: save and restore named iTerm2 workspaces (windows, tabs, split panes, folders, Claude).

  a51-ws save [-y] [NAME]  save everything open in iTerm2 right now (default name: last).
                        If NAME already exists you are asked before it is replaced; -y (--yes) skips the question.
  a51-ws up [NAME]      rebuild a saved workspace in new iTerm2 windows (default name: last)
  a51-ws list           list saved workspaces
  a51-ws show NAME      print a saved workspace as a readable tree
  a51-ws rm NAME        delete a saved workspace
  a51-ws --version      print the version

Saved files live in ~/.config/a51-ws/NAME.json (plain JSON, safe to hand-edit).
Set A51_WS_FOLDER to keep them somewhere else. Set A51_WS_DEBUG=1 to see full error details.
Only `claude` is restarted automatically (as `claude --continue || claude`). Other commands
(deploys, kubectl, ssh) are never re-run for you; each pane just opens in its folder.
"""
import os
import sys

import iterm2

from a51_ws import store
from a51_ws._version import __version__
from a51_ws.store import WorkspaceError

DEFAULT_WORKSPACE_NAME = "last"
CLAUDE_START_COMMAND = "claude --continue || claude\n"

ITERM2_UNREACHABLE_HELP = (
    "Could not connect to iTerm2. Check that iTerm2 is running and that its Python API is on:\n"
    "  iTerm2 > Settings > General > Magic > Enable Python API")


# ---------------------------------------------------------------- saving

APPEARANCE_KEY_WORDS = (
    "Font", "Color", "Spacing", "Transparency", "Blur", "Cursor Type", "Minimum Contrast",
    "Brighten Bold", "Use Bold", "Use Italic", "Thin Strokes", "Anti Aliased", "Background Image",
)


def appearance_only(all_properties):
    """The look of a pane: fonts, every color, spacing, transparency (includes Cmd +/- zoom)."""
    return {key: value for key, value in all_properties.items()
            if any(word in key for word in APPEARANCE_KEY_WORDS)}


async def describe_pane(session):
    folder = await session.async_get_variable("path")
    foreground_job = await session.async_get_variable("jobName") or ""
    profile_name = await session.async_get_variable("profileName")
    live_profile = await session.async_get_profile()
    return {
        "type": "pane",
        "folder": folder,
        "profile": profile_name,
        "runs_claude": "claude" in foreground_job.lower(),
        "appearance": appearance_only(live_profile.all_properties),
    }


async def describe_layout(node):
    """node is an iterm2 Session (one pane) or Splitter (panes side by side or stacked)."""
    if isinstance(node, iterm2.Session):
        return await describe_pane(node)
    return {
        "type": "split",
        "side_by_side": node.vertical,
        "children": [await describe_layout(child) for child in node.children],
    }


async def describe_tab(tab):
    """A tab's layout plus the title the person gave it (None when iTerm2 names it automatically)."""
    tab_layout = await describe_layout(tab.root)
    tab_layout["tab_title"] = await tab.async_get_variable("titleOverride") or None
    return tab_layout


async def save_workspace(connection, name):
    store.check_workspace_name(name)
    app = await iterm2.async_get_app(connection)
    saved_windows = []
    for window in app.terminal_windows:
        frame = await window.async_get_frame()
        saved_windows.append({
            "frame": [frame.origin.x, frame.origin.y, frame.size.width, frame.size.height],
            "tabs": [await describe_tab(tab) for tab in window.tabs],
        })
    if not saved_windows:
        raise WorkspaceError("No iTerm2 windows are open, so nothing was saved.")
    path, replaced_existing = store.save_workspace_file(name, saved_windows)
    pane_count = sum(store.count_panes(tab) for window in saved_windows for tab in window["tabs"])
    tab_count = sum(len(window["tabs"]) for window in saved_windows)
    verb = "Replaced" if replaced_existing else "Saved"
    print(f"{verb} '{name}': {len(saved_windows)} window(s), {tab_count} tab(s), {pane_count} pane(s)"
          f" -> {path}")


# ---------------------------------------------------------------- restoring

def folder_customization(pane):
    """Profile settings for a new pane: its folder plus its saved fonts and colors."""
    folder = pane.get("folder")
    customization = iterm2.LocalWriteOnlyProfile()
    for key, value in pane.get("appearance", {}).items():
        try:
            customization._simple_set(key, value)
        except Exception:
            pass  # an iTerm2 setting this version does not know: skip it, keep the rest of the look
    if folder and os.path.isdir(folder):
        customization.set_initial_directory_mode(
            iterm2.InitialWorkingDirectory.INITIAL_WORKING_DIRECTORY_CUSTOM)
        customization.set_custom_directory(folder)
    return customization


def folders_that_no_longer_exist(saved):
    missing = set()

    def visit(node):
        if node["type"] == "pane":
            folder = node.get("folder")
            if folder and not os.path.isdir(folder):
                missing.add(folder)
        else:
            for child in node["children"]:
                visit(child)

    for window in saved["windows"]:
        for tab in window["tabs"]:
            visit(tab)
    return sorted(missing)


async def build_layout(node, session, panes_to_start_claude):
    """Fill `session` (already created, already in the right folder) with the saved layout."""
    if node["type"] == "pane":
        if node.get("runs_claude", False):
            panes_to_start_claude.append(session)
        return
    sessions_for_children = [session]
    for child in node["children"][1:]:
        new_session = await sessions_for_children[-1].async_split_pane(
            vertical=node.get("side_by_side", False),
            profile_customizations=folder_customization(store.first_pane(child)),
        )
        sessions_for_children.append(new_session)
    for child, child_session in zip(node["children"], sessions_for_children):
        await build_layout(child, child_session, panes_to_start_claude)


async def restore_tab_title(tab, tab_layout):
    title = tab_layout.get("tab_title")
    if not title:
        return
    try:
        await tab.async_set_title(title)
    except Exception:
        print(f"Warning: tab title '{title}' could not be set; that tab keeps its automatic title.",
              file=sys.stderr)


async def restore_window(connection, saved_window, panes_to_start_claude):
    first_tab_layout = saved_window["tabs"][0]
    window = await iterm2.Window.async_create(
        connection,
        profile_customizations=folder_customization(store.first_pane(first_tab_layout)))
    if window is None:
        raise WorkspaceError("iTerm2 did not create a window.")
    await build_layout(first_tab_layout, window.current_tab.current_session, panes_to_start_claude)
    await restore_tab_title(window.current_tab, first_tab_layout)
    for tab_layout in saved_window["tabs"][1:]:
        tab = await window.async_create_tab(
            profile_customizations=folder_customization(store.first_pane(tab_layout)))
        await build_layout(tab_layout, tab.current_session, panes_to_start_claude)
        await restore_tab_title(tab, tab_layout)
    await window.tabs[0].async_select()
    try:
        x, y, width, height = saved_window["frame"]
        await window.async_set_frame(iterm2.Frame(iterm2.Point(x, y), iterm2.Size(width, height)))
    except Exception:
        pass  # no saved size, or a different screen setup: keep the default size


async def restore_workspace(connection, name):
    saved = store.load_workspace(name)
    for folder in folders_that_no_longer_exist(saved):
        print(f"Warning: folder {folder} no longer exists; panes that used it open in your home folder.",
              file=sys.stderr)
    await iterm2.async_get_app(connection)  # must be fetched once before creating windows or splits
    panes_to_start_claude = []
    failed_window_numbers = []
    for window_number, saved_window in enumerate(saved["windows"], 1):
        try:
            await restore_window(connection, saved_window, panes_to_start_claude)
        except Exception as error:  # keep going: one bad window must not lose the others
            failed_window_numbers.append(window_number)
            print(f"Warning: window {window_number} could not be restored ({error}).", file=sys.stderr)
    for session in panes_to_start_claude:
        await session.async_send_text(CLAUDE_START_COMMAND)
    print(f"Restored '{name}'. Claude restarted in {len(panes_to_start_claude)} pane(s).")
    if failed_window_numbers:
        raise WorkspaceError(
            f"{len(failed_window_numbers)} of {len(saved['windows'])} window(s) could not be restored.")


# ---------------------------------------------------------------- listing

def print_tree(node, indent=""):
    if node["type"] == "pane":
        marker = "  [claude]" if node.get("runs_claude", False) else ""
        print(f"{indent}- {node.get('folder') or '(no folder)'}{marker}")
        return
    direction = "side by side" if node.get("side_by_side", False) else "stacked"
    print(f"{indent}+ {direction}")
    for child in node["children"]:
        print_tree(child, indent + "    ")


def show_workspace(name):
    for window_number, window in enumerate(store.load_workspace(name)["windows"], 1):
        print(f"Window {window_number}")
        for tab_number, tab in enumerate(window["tabs"], 1):
            title = f'  "{tab["tab_title"]}"' if tab.get("tab_title") else ""
            print(f"  Tab {tab_number}{title}")
            print_tree(tab, "    ")


def list_workspaces():
    summaries = store.list_workspace_summaries()
    if not summaries:
        print("No saved workspaces yet. Arrange iTerm2, then run: a51-ws save NAME")
    for name, tab_count in summaries:
        description = f"{tab_count} tab(s)" if tab_count is not None else "UNREADABLE (see: a51-ws show)"
        print(f"{name:20} {description}")


def remove_workspace(name):
    if store.remove_workspace_file(name):
        print(f"Removed '{name}'.")
    else:
        raise WorkspaceError(f"No saved workspace called '{name}'. Try: a51-ws list")


# ---------------------------------------------------------------- command line

def read_answer(question):
    return input(question)


def input_is_interactive():
    return sys.stdin.isatty()


def confirm_overwrite(name):
    """Ask the usual Unix way: [y/N]. Only 'y' or 'yes' means yes; anything else, or end of input, is no."""
    if not input_is_interactive():
        raise WorkspaceError(
            f"Workspace '{name}' already exists and there is no terminal to ask you. "
            "Run again with --yes to overwrite it.")
    try:
        answer = read_answer(f"Workspace '{name}' already exists. Overwrite it? [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() in ("y", "yes"):
        return True
    raise WorkspaceError(f"Not saved. Workspace '{name}' was left as it was.")


def check_before_saving(name, skip_question):
    """Runs before iTerm2 is touched, so answering no stops everything cleanly."""
    kind, stored_name = store.lookup_workspace(name)
    if kind == "different_case":
        store.refuse_different_case(name, stored_name)
    if kind == "exact" and not skip_question:
        confirm_overwrite(name)

def run_against_iterm2(action):
    """Run an iTerm2 action, turning 'cannot reach iTerm2' into a plain-English message."""
    try:
        iterm2.run_until_complete(action, retry=False)
    except (WorkspaceError, KeyboardInterrupt):
        raise
    except Exception as error:
        if os.environ.get("A51_WS_DEBUG"):
            raise
        raise WorkspaceError(f"{ITERM2_UNREACHABLE_HELP}\n(details: {type(error).__name__}: {error})") from None


def run_command(command, name, explicit_name, skip_question=False):
    if command == "save":
        check_before_saving(name, skip_question)
        run_against_iterm2(lambda connection: save_workspace(connection, name))
    elif command == "up":
        run_against_iterm2(lambda connection: restore_workspace(connection, name))
    elif command == "list":
        list_workspaces()
    elif command in ("show", "rm"):
        if not explicit_name:
            raise WorkspaceError(f"'{command}' needs a workspace name. Try: a51-ws list")
        (show_workspace if command == "show" else remove_workspace)(name)


def main(arguments=None):
    """Return the process exit code: 0 ok, 1 a problem the person can fix, 2 wrong usage."""
    arguments = sys.argv[1:] if arguments is None else arguments
    command = arguments[0] if arguments else "help"
    if command in ("help", "-h", "--help"):
        print(__doc__)
        return 0
    if command in ("--version", "version"):
        print(f"a51-ws {__version__}")
        return 0
    skip_question = command == "save" and any(word in ("-y", "--yes") for word in arguments[1:])
    if skip_question:
        arguments = [word for word in arguments if word not in ("-y", "--yes")]
    takes_no_name = command in ("list", "--version", "version")
    if command not in ("save", "up", "list", "show", "rm") or len(arguments) > (1 if takes_no_name else 2):
        print(f"a51-ws: unknown or malformed command: {' '.join(arguments)}\n", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 2
    explicit_name = len(arguments) > 1
    name = arguments[1] if explicit_name else DEFAULT_WORKSPACE_NAME
    try:
        run_command(command, name, explicit_name, skip_question)
    except WorkspaceError as error:
        print(f"a51-ws: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\na51-ws: interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
