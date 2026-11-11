from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from plugin import COMMAND_RE
from test_plugin import loadout_plugin, session_slots


def make_plugin(data_dir: Path):
    replies: list[str] = []
    plugin, rendered, _ = loadout_plugin(replies)
    plugin._cfg = {"allowed_groups": ["100", "200"], "admin_users": ["900"]}
    plugin._data_dir_path = data_dir
    return plugin, replies, rendered


async def command(plugin, text, user="700", group="100", *, through_host=False):
    kwargs = {"text": text, "stream_id": "s", "user_id": user, "group_id": group}
    if through_host:
        match = COMMAND_RE.fullmatch(text)
        assert match is not None
        kwargs.update(text="", matched_groups=match.groupdict())
    return await plugin.handle_command(**kwargs)


def test_experiment_whitelist_is_managed_by_admin_per_group_and_persists(tmp_path):
    async def scenario():
        plugin, replies, rendered = make_plugin(tmp_path)
        assert not (await command(plugin, "/hd exp on"))[0]
        assert "管理员" in replies[-1]
        assert not (await command(plugin, "/hd exp on", user="900", group="300"))[0]
        assert not (await command(plugin, "/hd exp on", user="900", group=""))[0]
        assert not (await command(plugin, "/hd exp loadout"))[0]
        assert "未启用" in replies[-1]
        assert not rendered

        assert (await command(plugin, "/hd exp on", user="900", through_host=True))[0]
        assert (await command(plugin, "/hd exp status", user="900"))[0]
        assert "已启用" in replies[-1]
        assert (await command(plugin, "/hd exp status", user="900", group="200"))[0]
        assert "未启用" in replies[-1]
        assert not (await command(plugin, "/hd exp loadout", group="200"))[0]
        assert not (await command(plugin, "/hd exp off 100", user="900"))[0]
        assert (tmp_path / "experimental_groups.json").is_file()

        restarted, replies, _ = make_plugin(tmp_path)
        assert (await command(restarted, "/潜兵 exp presets 东线", through_host=True))[0]
        assert "bug_cave_clear" in replies[-1]
        assert (await command(restarted, "/hd exp off", user="900"))[0]
        assert not (await command(restarted, "/hd exp loadout"))[0]

    asyncio.run(scenario())


def test_experiment_draw_and_reroll_keep_separate_sessions_and_mark_output(tmp_path):
    async def scenario():
        plugin, replies, rendered = make_plugin(tmp_path)
        assert (await command(plugin, "/hd loadout"))[0]
        ordinary = session_slots(plugin, "s|700")
        assert (await command(plugin, "/hd exp on", user="900"))[0]
        assert not (await command(plugin, "/hd exp loadout 4"))[0]
        assert (await command(plugin, "/hd exp loadout bug_support_rotation", through_host=True))[0]
        assert "实验配装" in rendered[-1] and "机枪加次抛" in rendered[-1]
        assert session_slots(plugin, "s|700") == ordinary

        before = dict(plugin._experimental_sessions[("100", "s|700")].loadout)
        assert not (await command(plugin, "/hd exp loadout 4", user="701"))[0]
        assert (await command(plugin, "/hd exp loadout 4", through_host=True))[0]
        after = plugin._experimental_sessions[("100", "s|700")].loadout
        assert {key for key in before if before[key] != after[key]} == {"booster"}
        assert "机枪加次抛" in rendered[-1]

        assert (await command(plugin, "/hd exp off", user="900"))[0]
        assert (await command(plugin, "/hd exp on", user="900"))[0]
        assert not (await command(plugin, "/hd exp loadout 4"))[0]
        assert session_slots(plugin, "s|700") == ordinary

        async def no_render(*args, **kwargs):
            return ""

        plugin._render_card = no_render
        assert (await command(plugin, "/hd exp loadout terminids"))[0]
        assert "实验配装" in replies[-1] and "东线" in replies[-1]

    asyncio.run(scenario())


@pytest.mark.parametrize("blocked", ["exp", "loadout"])
def test_experiment_applies_the_command_blacklist(tmp_path, blocked):
    async def scenario():
        plugin, replies, rendered = make_plugin(tmp_path)
        plugin._cfg["command_blacklist"] = {blocked: ["700"]}
        assert (await command(plugin, "/hd exp on", user="900"))[0]
        assert not (await command(plugin, "/hd exp loadout"))[0]
        assert "禁止" in replies[-1]
        assert not rendered

    asyncio.run(scenario())


def test_experiment_corrupt_allowlist_reports_failure_without_breaking_normal_draw(tmp_path):
    async def scenario():
        plugin, replies, rendered = make_plugin(tmp_path)
        path = tmp_path / "experimental_groups.json"
        path.write_text("{", encoding="utf-8")
        assert not (await command(plugin, "/hd exp on", user="900"))[0]
        assert "白名单" in replies[-1]
        assert not (await command(plugin, "/hd exp loadout"))[0]
        assert not rendered
        assert path.read_text(encoding="utf-8") == "{"
        assert (await command(plugin, "/hd loadout"))[0]

    asyncio.run(scenario())



def test_experiment_reroll_expiry_and_group_scope(tmp_path):
    from dataclasses import replace

    async def scenario():
        plugin, replies, rendered = make_plugin(tmp_path)
        for group in ("100", "200"):
            assert (await command(plugin, "/hd exp on", user="900", group=group))[0]
        assert (await command(plugin, "/hd exp loadout field_medic"))[0]
        assert not (await command(plugin, "/hd exp loadout 4", group="200"))[0]
        assert not (await command(plugin, "/hd exp loadout 2"))[0]
        assert "没有符合原模板" in replies[-1]
        assert len(rendered) == 1
        key = "100", "s|700"
        session = plugin._experimental_sessions[key]
        plugin._experimental_sessions[key] = replace(session, updated_at=session.updated_at - 121)
        assert not (await command(plugin, "/hd exp loadout 四"))[0]
        assert "没有可重抽" in replies[-1]
        assert key not in plugin._experimental_sessions

    asyncio.run(scenario())


def test_experiment_persists_on_older_hosts_under_runtime_data(tmp_path, monkeypatch):
    import plugin as plugin_module

    monkeypatch.setattr(plugin_module, "BUNDLE_DIR", tmp_path)

    async def scenario():
        plugin, _, _ = make_plugin(tmp_path)
        assert (await command(plugin, "/hd exp on", user="900"))[0]
        assert (tmp_path / "data" / "experimental_groups.json").is_file()

    asyncio.run(scenario())
