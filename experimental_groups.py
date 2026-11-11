"""Persistent group opt-ins for experimental commands."""

import json
from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock


class ExperimentalGroupsError(Exception):
    """The group opt-ins could not be read or saved."""


class ExperimentalGroups:
    # ponytail: one process-wide lock serializes the small file operations across instances.
    _lock = Lock()

    def __init__(self, path: Path):
        self._path = path

    def enabled(self, group_id: str) -> bool:
        with self._lock:
            return group_id in self._read()

    def set_enabled(self, group_id: str, enabled: bool) -> bool:
        with self._lock:
            groups = self._read()
            if (group_id in groups) == enabled:
                return False
            if enabled:
                groups.add(group_id)
            else:
                groups.remove(group_id)
            self._write(groups)
            return True

    def _read(self) -> set[str]:
        try:
            groups = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return set()
        except (OSError, ValueError) as exc:
            raise ExperimentalGroupsError(f"无法读取实验功能群名单 {self._path.name}：{exc}") from exc
        if not isinstance(groups, list) or not all(isinstance(group, str) for group in groups):
            raise ExperimentalGroupsError(f"实验功能群名单 {self._path.name} 必须是群号字符串数组")
        return set(groups)

    def _write(self, groups: set[str]) -> None:
        temporary = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self._path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(sorted(groups), stream, indent=2)
                stream.write("\n")
            temporary.replace(self._path)
        except OSError as exc:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)
            raise ExperimentalGroupsError(f"无法保存实验功能群名单 {self._path.name}：{exc}") from exc
