import json
import os
import threading

import pytest

from a51_ws import store
from a51_ws.store import WorkspaceError
from conftest import pane


# ---- names

@pytest.mark.parametrize("name", ["work", "myproject", "my-project_2", "v1.2", "A"])
def test_good_names_are_accepted(name):
    assert store.check_workspace_name(name) == name


@pytest.mark.parametrize("name", ["", "../escape", "a/b", ".hidden", "-lead", "has space", "x" * 65,
                                  "tab\tname", "new\nline", "naïve", "a\x00b"])
def test_unsafe_names_are_refused(name):
    with pytest.raises(WorkspaceError, match="not a usable workspace name"):
        store.check_workspace_name(name)


def test_folder_defaults_under_home_and_honors_override(monkeypatch, tmp_path):
    monkeypatch.delenv("A51_WS_FOLDER", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert store.workspaces_folder() == tmp_path / ".config" / "a51-ws"
    monkeypatch.setenv("A51_WS_FOLDER", "~/elsewhere")
    assert store.workspaces_folder() == tmp_path / "elsewhere"


# ---- validation of hand-edited files

def test_valid_workspace_passes(sample_windows):
    assert store.check_workspace({"windows": sample_windows}) is not None


@pytest.mark.parametrize("broken, message", [
    ([], "JSON object"),
    ({}, "non-empty 'windows'"),
    ({"windows": []}, "non-empty 'windows'"),
    ({"windows": ["x"]}, "expected an object"),
    ({"windows": [{"tabs": []}]}, "non-empty 'tabs'"),
    ({"windows": [{"tabs": [{"type": "blob"}]}]}, "'pane' or 'split'"),
    ({"windows": [{"tabs": [{"type": "split", "children": []}]}]}, "non-empty 'children'"),
    ({"windows": [{"tabs": [{"type": "pane", "folder": 7}]}]}, "'folder' must be text"),
    ({"windows": [{"tabs": [{"type": "pane", "runs_claude": "yes"}]}]}, "true or false"),
    ({"windows": [{"frame": [1, 2], "tabs": [{"type": "pane"}]}]}, "four numbers"),
    ({"windows": [{"frame": [True, 0, 1, 1], "tabs": [{"type": "pane"}]}]}, "four numbers"),
    ({"windows": [{"tabs": [{"type": "pane", "tab_title": 7}]}]}, "'tab_title' must be text"),
    ({"windows": [{"tabs": [{"type": "pane", "tab_title": "x" * 201}]}]}, "'tab_title' is too long"),
    ({"format_version": 99, "windows": [{"tabs": [{"type": "pane"}]}]}, "newer a51-ws"),
])
def test_damaged_files_are_refused_with_a_clear_message(broken, message):
    with pytest.raises(WorkspaceError, match=message):
        store.check_workspace(broken)


def test_deeply_nested_splits_are_refused_not_a_recursion_crash():
    node = pane("/x")
    for _ in range(store.MAXIMUM_SPLIT_DEPTH + 5):
        node = {"type": "split", "side_by_side": True, "children": [node]}
    with pytest.raises(WorkspaceError, match="nested"):
        store.check_workspace({"windows": [{"tabs": [node]}]})


def test_file_without_format_version_still_loads(isolated_workspaces_folder, sample_windows):
    (isolated_workspaces_folder / "old.json").write_text(json.dumps({"windows": sample_windows}))
    assert store.load_workspace("old")["windows"]


# ---- reading and writing

def test_load_missing_workspace_says_how_to_list(isolated_workspaces_folder):
    with pytest.raises(WorkspaceError, match="No saved workspace called 'nope'"):
        store.load_workspace("nope")


def test_load_corrupt_json_names_the_file_and_the_line(isolated_workspaces_folder):
    (isolated_workspaces_folder / "bad.json").write_text('{"windows": [\n  oops')
    with pytest.raises(WorkspaceError, match=r"bad\.json is not valid JSON .*line 2"):
        store.load_workspace("bad")


def test_save_then_load_round_trips_and_reports_replacement(isolated_workspaces_folder, sample_windows):
    path, replaced = store.save_workspace_file("work", sample_windows)
    assert path == isolated_workspaces_folder / "work.json" and replaced is False
    assert store.load_workspace("work")["windows"] == sample_windows
    assert store.save_workspace_file("work", sample_windows)[1] is True


def test_save_creates_a_missing_folder(tmp_path, monkeypatch, sample_windows):
    monkeypatch.setenv("A51_WS_FOLDER", str(tmp_path / "deep" / "new"))
    store.save_workspace_file("work", sample_windows)
    assert (tmp_path / "deep" / "new" / "work.json").exists()


def test_failed_save_leaves_the_old_file_intact_and_no_temp_files(
        isolated_workspaces_folder, sample_windows, monkeypatch):
    store.save_workspace_file("work", sample_windows)
    before = (isolated_workspaces_folder / "work.json").read_text()

    def explode(*_):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(os, "replace", explode)
    with pytest.raises(WorkspaceError, match="Could not save"):
        store.save_workspace_file("work", [{"tabs": [pane("/changed")]}])
    assert (isolated_workspaces_folder / "work.json").read_text() == before


def test_save_into_unwritable_place_is_a_clear_error(tmp_path, monkeypatch, sample_windows):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder")
    monkeypatch.setenv("A51_WS_FOLDER", str(blocker / "inside"))
    with pytest.raises(WorkspaceError, match="Could not save"):
        store.save_workspace_file("work", sample_windows)


def test_concurrent_saves_never_leave_a_corrupt_file(isolated_workspaces_folder, sample_windows):
    threads = [threading.Thread(target=store.save_workspace_file, args=("work", sample_windows))
               for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert store.load_workspace("work")["windows"] == sample_windows


def test_remove_reports_whether_anything_was_removed(isolated_workspaces_folder, sample_windows):
    store.save_workspace_file("old", sample_windows)
    assert store.remove_workspace_file("old") is True
    assert store.remove_workspace_file("old") is False


def test_summaries_flag_damaged_files_and_ignore_strangers(isolated_workspaces_folder, sample_windows):
    store.save_workspace_file("good", sample_windows)
    (isolated_workspaces_folder / "broken.json").write_text("{nope")
    (isolated_workspaces_folder / "not a name.json").write_text("{}")
    assert store.list_workspace_summaries() == [("broken", None), ("good", 2)]


def test_summaries_for_a_folder_that_does_not_exist_yet(tmp_path, monkeypatch):
    monkeypatch.setenv("A51_WS_FOLDER", str(tmp_path / "missing"))
    assert store.list_workspace_summaries() == []


def test_count_and_first_pane(sample_windows):
    split = sample_windows[0]["tabs"][1]
    assert store.count_panes(split) == 2
    assert store.first_pane(split)["folder"] == "/work/b"


def test_tab_title_none_and_text_are_both_valid():
    for title in (None, "BUILDS", ""):
        store.check_workspace({"windows": [{"tabs": [{"type": "pane", "tab_title": title}]}]})


# ---- exact-case lookup (macOS disks ignore case, a51-ws names do not)

def test_lookup_reports_exact_missing_and_different_case(isolated_workspaces_folder, sample_windows):
    store.save_workspace_file("work", sample_windows)
    assert store.lookup_workspace("work") == ("exact", "work")
    assert store.lookup_workspace("Work") == ("different_case", "work")
    assert store.lookup_workspace("other") == ("missing", None)


def test_lookup_in_a_folder_that_does_not_exist_yet(tmp_path, monkeypatch):
    monkeypatch.setenv("A51_WS_FOLDER", str(tmp_path / "nope"))
    assert store.lookup_workspace("work") == ("missing", None)


def test_save_refuses_a_name_that_differs_only_by_case(isolated_workspaces_folder, sample_windows):
    store.save_workspace_file("work", sample_windows)
    with pytest.raises(WorkspaceError, match="differs only by capital letters from 'work'"):
        store.save_workspace_file("Work", [{"tabs": [pane("/other")]}])
    assert store.load_workspace("work")["windows"] == sample_windows  # untouched


def test_load_and_remove_of_a_different_case_name_suggest_the_real_one(
        isolated_workspaces_folder, sample_windows):
    store.save_workspace_file("work", sample_windows)
    with pytest.raises(WorkspaceError, match="Did you mean 'work'"):
        store.load_workspace("WORK")
    with pytest.raises(WorkspaceError, match="Did you mean 'work'"):
        store.remove_workspace_file("WORK")
    assert store.lookup_workspace("work")[0] == "exact"  # nothing was deleted
