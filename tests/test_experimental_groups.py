"""Persistence for the group opt-in list."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from experimental_groups import ExperimentalGroups, ExperimentalGroupsError


def test_missing_file_leaves_all_groups_disabled(tmp_path):
    path = tmp_path / "data" / "experimental_groups.json"
    groups = ExperimentalGroups(path)

    assert not groups.enabled("123")
    assert not groups.set_enabled("123", False)
    assert not path.exists()


def test_group_changes_survive_reopening_the_file(tmp_path):
    path = tmp_path / "data" / "experimental_groups.json"
    groups = ExperimentalGroups(path)

    assert groups.set_enabled("123", True)
    assert not groups.set_enabled("123", True)
    assert groups.set_enabled("456", True)

    reopened = ExperimentalGroups(path)
    assert reopened.enabled("123")
    assert reopened.enabled("456")
    assert not reopened.enabled("789")
    assert reopened.set_enabled("123", False)
    assert not ExperimentalGroups(path).enabled("123")
    assert ExperimentalGroups(path).enabled("456")


@pytest.mark.parametrize("content", [b"[", b'{"123": true}', b'["123", 456]', b"\xff"])
def test_corrupt_file_is_reported_and_preserved(tmp_path, content):
    path = tmp_path / "experimental_groups.json"
    path.write_bytes(content)
    groups = ExperimentalGroups(path)

    with pytest.raises(ExperimentalGroupsError):
        groups.enabled("123")
    with pytest.raises(ExperimentalGroupsError):
        groups.set_enabled("123", True)

    assert path.read_bytes() == content


def test_unreadable_file_is_reported(tmp_path):
    path = tmp_path / "experimental_groups.json"
    path.mkdir()

    with pytest.raises(ExperimentalGroupsError):
        ExperimentalGroups(path).enabled("123")


def test_failed_replace_preserves_existing_groups(tmp_path, monkeypatch):
    path = tmp_path / "experimental_groups.json"
    groups = ExperimentalGroups(path)
    assert groups.set_enabled("123", True)

    def reject_replace(source, target):
        raise PermissionError("cannot replace the data file")

    monkeypatch.setattr(type(path), "replace", reject_replace)
    with pytest.raises(ExperimentalGroupsError):
        groups.set_enabled("456", True)

    assert groups.enabled("123")
    assert not groups.enabled("456")
    assert set(tmp_path.iterdir()) == {path}


def test_concurrent_updates_keep_all_groups(tmp_path):
    path = tmp_path / "experimental_groups.json"
    group_ids = [str(number) for number in range(16)]

    def enable_group(group_id):
        return ExperimentalGroups(path).set_enabled(group_id, True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(enable_group, group_ids))

    groups = ExperimentalGroups(path)
    assert all(groups.enabled(group_id) for group_id in group_ids)
