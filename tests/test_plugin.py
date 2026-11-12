from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import random
import re
import unicodedata
import time

import pytest
from unittest.mock import patch
from pathlib import Path

from plugin import (
    ACTION_ALIASES,
    ADMIN_ACTIONS,
    ACTION_LABELS,
    BUNDLE_DIR,
    COMMAND_ACTIONS,
    COMMAND_ALIASES,
    COMMAND_NAME,
    COMMAND_RE,
    COMMAND_PATTERN,
    COMMAND_RPC_TIMEOUT_MS,
    COMMAND_TRIGGERS,
    DIAG_HTML,
    FUNCTIONAL_ACTIONS,
    HELP_ONLY_ALIASES,
    HELP_TOPICS,
    LETTER_SHORTCUTS,
    LOADOUT_CARD_HEIGHT,
    LOADOUT_CARD_WIDTH,
    DemocracyChoosesPlugin,
    LOADOUT_REROLL_TTL_SECONDS,
    LOADOUT_STRATAGEM_COUNT,
    PluginConfig,
    PluginSection,
    RENDER_RPC_TIMEOUT_MS,
    SINGLE_CHAR_SHORTCUTS,
    format_loadout,
    generate_loadout,
    load_loadout_icons,
    load_loadout_pool,
    pad_display,
    render_loadout_html,
    usage_hint,
)


def command_plugin(replies: list[str]) -> DemocracyChoosesPlugin:
    """Capture replies at the platform boundary; keep command behavior real."""
    plugin = DemocracyChoosesPlugin()
    plugin._cfg = {"allowed_groups": ["100", "2"]}

    async def reply(kwargs: object, message: str) -> bool:
        replies.append(message)
        return True

    plugin._reply = reply  # type: ignore[method-assign]
    return plugin


def test_reply_sends_text_to_the_originating_stream() -> None:
    async def scenario() -> None:
        plugin = DemocracyChoosesPlugin()
        calls: list[tuple[object, object]] = []

        class FakeSend:
            async def text(self, text: object = None, stream_id: object = None) -> bool:
                calls.append((text, stream_id))
                return True

        class FakeCtx:
            send = FakeSend()

        attach_ctx(plugin, FakeCtx())
        assert await plugin._reply({"stream_id": "s-9"}, "hello")
        assert calls == [("hello", "s-9")]
        assert not await plugin._reply({}, "no stream")
        assert len(calls) == 1

    asyncio.run(scenario())


def test_trigger_aliases_stay_in_sync_with_the_pattern_and_the_decorator() -> None:
    """The regex, the registered aliases and the parser must come from one list."""
    assert COMMAND_TRIGGERS[0] == COMMAND_NAME
    assert COMMAND_ALIASES == tuple(f"/{name}" for name in COMMAND_TRIGGERS[1:])
    for name in COMMAND_TRIGGERS:
        assert COMMAND_RE.match(f"/{name}") is not None, f"/{name} 不被命令正则接受"
        assert COMMAND_RE.match(f"/{name} status") is not None, f"/{name} status 解析失败"
    # The host prefix-matches every incoming message against these, so a bare word
    # would swallow ordinary chat -- they must all keep the leading slash.
    for alias in COMMAND_ALIASES:
        assert alias.startswith("/"), f"别名 {alias} 没有 / 前缀，会误伤普通聊天"


def test_command_decorator_registers_exactly_the_documented_aliases() -> None:
    info = getattr(DemocracyChoosesPlugin.handle_command, "__maibot_component_info__", None)
    assert info is not None, "命令缺少组件元数据"
    meta = dict(getattr(info, "metadata", info) or {})
    aliases = list(getattr(info, "aliases", meta.get("aliases", [])) or [])
    assert aliases == list(COMMAND_ALIASES)
    pattern = getattr(info, "command_pattern", None) or meta.get("command_pattern")
    assert pattern == COMMAND_PATTERN


def test_every_short_form_maps_to_a_real_target() -> None:
    for alias, action in ACTION_ALIASES.items():
        assert action in COMMAND_ACTIONS, f"动作别名 {alias} -> {action} 不是真实动作"
    for alias, topic in HELP_ONLY_ALIASES.items():
        assert topic in HELP_TOPICS, f"主题别名 {alias} -> {topic} 不是真实主题"


def test_letter_and_single_character_shortcuts_resolve() -> None:
    plugin = command_plugin([])
    # The tables are the source of truth; the alias dict must agree with them.
    for shortcut, action in (*LETTER_SHORTCUTS, *SINGLE_CHAR_SHORTCUTS):
        assert ACTION_ALIASES.get(shortcut) == action, f"简写 {shortcut} 没有映射到 {action}"
    # ...and each resolves end-to-end through the parser, on every trigger.
    for shortcut, action in (*LETTER_SHORTCUTS, *SINGLE_CHAR_SHORTCUTS):
        assert plugin._resolve_command({"text": f"/hd {shortcut}"})[0] == action
        assert plugin._resolve_command({"text": f"/helldivers {shortcut}"})[0] == action


def test_pad_display_accounts_for_wide_characters() -> None:
    """CJK glyphs take two columns, so plain ``ljust`` produces ragged tables."""
    assert pad_display("sub", 8) == "sub     "
    assert pad_display("订阅", 8) == "订阅    "  # 4 columns used, 4 spaces left
    assert pad_display("取消订阅", 12) == "取消订阅    "
    assert pad_display("toolongvalue", 4) == "toolongvalue"


def test_shortcut_table_rows_share_one_display_width() -> None:
    plugin = command_plugin([])
    rows = plugin._help_text("shortcut").splitlines()
    suffixes = tuple(f"/hd {shortcut}" for shortcut, _ in LETTER_SHORTCUTS)
    table = [row for row in rows if row.startswith("  ") and row.rstrip().endswith(suffixes)]
    assert len(table) == len(LETTER_SHORTCUTS), f"简写表只渲染出 {len(table)} 行"
    widths = {
        sum(2 if unicodedata.east_asian_width(ch) in {"W", "F"} else 1 for ch in row.split("/hd ")[0])
        for row in table
    }
    assert len(widths) == 1, f"简写表列宽不一致：{sorted(widths)}"


def test_shortcut_tables_are_fully_documented_in_the_help() -> None:
    """``topic_shortcut`` and ``usage_hint`` render from the tables, so they agree."""
    plugin = command_plugin([])
    body = plugin._help_text("shortcut")
    hint = plugin._usage_hint()
    for shortcut, action in LETTER_SHORTCUTS:
        assert f"/hd {shortcut}" in body, f"字母简写 {shortcut} 未在简写说明里列出"
        assert f"{shortcut} {ACTION_LABELS[action]}" in hint
    for shortcut, action in SINGLE_CHAR_SHORTCUTS:
        assert f"{shortcut}={ACTION_LABELS[action]}" in body, f"单字简写 {shortcut} 未列出"


def test_letter_shortcuts_work_across_every_trigger() -> None:
    plugin = command_plugin([])
    for trigger in COMMAND_TRIGGERS:
        action, argument = plugin._resolve_command({"text": f"/{trigger} lo 三"})
        assert (action, argument) == ("loadout", "三"), f"/{trigger} lo 三 解析错误"


def test_unparseable_command_is_refused_instead_of_running_a_default() -> None:
    """``/hdx`` only reaches us because the host alias check is ``startswith``."""

    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)
        ok, why, _ = await plugin.handle_command(text="/hdx", stream_id="s", group_id="100")
        assert ok is False
        assert "没看懂" in replies[-1] and "用法：" in replies[-1]
        assert plugin._loadout_sessions == {}
        assert why

    asyncio.run(scenario())


def test_shortcut_help_topic_is_reachable_by_short_and_chinese_names() -> None:
    plugin = command_plugin([])
    body = plugin._help_text("简写")
    assert body == plugin._help_text("shortcut")
    assert body.startswith("【/helldivers")
    assert "中文写法" in body
    # ``/hd 简写`` is shorthand for ``help shortcut``.
    assert plugin._resolve_command({"text": "/hd 简写"}) == ("help", "shortcut")
    assert plugin._resolve_command({"text": "/hd h 简写"}) == ("help", "简写")


def test_short_trigger_runs_the_command_end_to_end() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)
        ok, _, _ = await plugin.handle_command(text="/hd 助", group_id="2", stream_id="s")
        assert ok and "用法" in replies[-1]
        ok, _, _ = await plugin.handle_command(text="/潜兵 st", group_id="2", stream_id="s")
        assert ok and "配装" in replies[-1]

    asyncio.run(scenario())


def test_command_answers_alias_and_unknown_action_in_an_allowed_group() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)
        ok, _, _ = await plugin.handle_command(text="/helldivers 帮助", stream_id="s", group_id="100")
        assert ok and "用法" in replies[-1]
        ok, _, _ = await plugin.handle_command(text="/helldivers 胡写", stream_id="s", group_id="100")
        assert ok is False and "未知子命令" in replies[-1]
        ok, _, _ = await plugin.handle_command(text="/helldivers status", stream_id="s", group_id="100")
        assert ok and "配装" in replies[-1]
        assert len(replies) == 3

    asyncio.run(scenario())


def test_loadout_pool_reads_every_slot() -> None:
    pool = load_loadout_pool()
    assert set(pool) == {"primary", "secondary", "grenade", "booster", "stratagem"}
    assert {slot: len(names) for slot, names in pool.items()} == {
        "primary": 56,
        "secondary": 26,
        "grenade": 24,
        "booster": 20,
        "stratagem": 95,
    }
    all_names = [name for names in pool.values() for name in names]
    assert all(isinstance(name, str) and name.strip() for name in all_names)
    assert len(all_names) == len(set(all_names)), "装备名称必须全局唯一"

    current_names = set(all_names)
    assert {
        "AR-2 野狼",
        "SMG/FLAM-34 司炉者",
        "CQC-73 堑壕工具",
        "AR-11 仲裁者",
        "P-34 爆破者",
        "G-60 反坦克追踪者",
        "额外消耗性反坦克武器配额",
        "集成灭火器",
        "40-K 热熔枪",
        "GR-8 无后坐力炮",
        "M-1000 重装机枪",
        "MS-11 单兵导弹发射井",
        "S-11 矛枪",
        "GL-28 弹链式榴弹发射器背包",
        "TD-110 风暴漩涡",
    } <= current_names
    assert {
        "AR-2 郊狼",
        "FLAM-34 炉管者",
        "CQC-72 堑壕工具",
        "AR-11 Arbitrator",
        "TD-110 Maelstrom",
    }.isdisjoint(current_names)
    assert all(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", name) for name in all_names)
    assert load_loadout_pool("does-not-exist.json") == {}


def test_generate_loadout_fills_eight_slots_without_duplicates() -> None:
    pool = {
        "primary": ["主武器甲"],
        "secondary": ["副武器乙"],
        "grenade": ["投掷物丙"],
        "booster": ["强化资源丁"],
        "stratagem": ["战备1", "战备2", "战备3", "战备4", "战备5"],
    }
    loadout = generate_loadout(pool, random.Random(7))
    assert loadout["primary"] == "主武器甲" and loadout["booster"] == "强化资源丁"
    stratagems = [loadout[f"stratagem_{index}"] for index in range(LOADOUT_STRATAGEM_COUNT)]
    assert len(set(stratagems)) == LOADOUT_STRATAGEM_COUNT
    assert set(stratagems) <= set(pool["stratagem"])
    assert generate_loadout({}, random.Random(1)) == {}


LOADOUT_SAMPLE = {
    "primary": "AR-23 解放者",
    "secondary": "P-2 和平制造者",
    "grenade": "G-12 高爆弹",
    "booster": "UAV侦察强化",
    "stratagem_0": "MG-43 机枪",
    "stratagem_1": "“飞鹰”500KG炸弹",
    "stratagem_2": "轨道激光炮",
    "stratagem_3": "SH-20 防弹护盾背包",
}


def test_render_loadout_html_inlines_icons_without_touching_the_network() -> None:
    icons = {name: "data:image/webp;base64,AAAA" for name in LOADOUT_SAMPLE.values()}
    page = render_loadout_html(LOADOUT_SAMPLE, motto="为了民主", icons=icons)
    for name in LOADOUT_SAMPLE.values():
        assert name in page
    assert "绝地潜兵 2：民主帮你选择" in page and "常规装备" in page and "战略配备" in page
    # Every card carries its reroll number as a badge, 1-8 in reading order.
    badges = re.findall(r'<b class="idx">(\d)</b>', page)
    assert badges == [str(index) for index in range(1, 9)]
    assert "为了民主" in page
    assert page.count('<img src="data:image/webp;base64,AAAA" alt="">') == len(LOADOUT_SAMPLE)
    # allow_network is off on the render capability, so nothing may be fetched.
    for marker in ("@import", "http://", "https://"):
        assert marker not in page


def test_render_loadout_html_without_icons_omits_images() -> None:
    page = render_loadout_html(LOADOUT_SAMPLE, motto="为了民主")
    assert "<img" not in page and "src=" not in page
    # A slot with no icon still shows its name rather than an empty frame.
    assert "AR-23 解放者" in page


def test_render_loadout_html_survives_an_item_missing_from_the_icon_file() -> None:
    sample = dict(LOADOUT_SAMPLE)
    sample["primary"] = "AR-11 仲裁者"
    page = render_loadout_html(sample, icons={"MG-43 机枪": "data:image/webp;base64,BBBB"})
    assert page.count("<img") == 1
    assert "MG-43 机枪" in page and "轨道激光" in page and "AR-11 仲裁者" in page
    assert (
        '<div class="card noicon"><div class="slot"><b class="idx">1</b>主武器</div>'
        '<div class="name">AR-11 仲裁者</div></div>'
    ) in page


def test_loadout_pool_includes_both_recent_warbonds_in_the_correct_slots() -> None:
    data = json.loads((MANIFEST_PATH.parent / "loadout_data.json").read_text(encoding="utf-8"))
    by_name = {item["name_en"]: item for item in data["items"]}
    expected = {
        "AR-11 Arbitrator": "primary",
        "GL-15 Evictor": "primary",
        "P-34 Breacher": "secondary",
        "G-60 Anti-Tank Seeker": "grenade",
        "G-8 Immolation": "grenade",
        "Surplus EAT Allocation": "booster",
        "Integrated Extinguishers": "booster",
        "R-40 Sightliner": "primary",
        "P-44 Mist": "secondary",
        "G-11 Caltrops": "grenade",
        "AMW-20 Apex": "stratagem",
        "LAS-44 Nova": "stratagem",
    }
    pool = load_loadout_pool()
    icons = load_loadout_icons()
    for english, slot in expected.items():
        item = by_name[english]
        assert item["slot"] == slot
        assert item["name"] in pool[slot] and item["name"] in icons


def test_refresher_resolves_support_names_from_developer_render_files() -> None:
    from tools.refresh_loadout_database import ListedItem, build_items

    rows = [
        ListedItem("AMW-20 Apex", "AMW-20 Apex", "Apex Stratagem Icon Background.svg", "stratagem"),
        ListedItem("LAS-44 Nova", "LAS-44 Nova", "Nova Stratagem Icon Background.svg", "stratagem"),
    ]
    localized = {
        "AMW-20 Apex Weapon and Backpack Support Render.png": ("AMW-20 尖峰", "AMW-20 尖峰"),
        "LAS-44 Nova Support Render.png": ("LAS-44 新星", "LAS-44 新星"),
    }
    items = build_items([], localized, {}, [], rows, [], {})
    assert {item["icon_file"] for item in items} == set(localized)
    assert all(item["translation_source"] == "zh_wiki_weapon_gallery" for item in items)


def test_refresher_downloads_a_thumbnail_when_cached_bytes_are_an_original() -> None:
    from tools.refresh_loadout_database import can_reuse_icon

    original = {"source_sha1": "a" * 40, "embedded_width": 2998, "embedded_height": 1868, "mime": "image/png"}
    thumbnail = {"sha1": "a" * 40, "embedded_width": 224, "embedded_height": 140, "mime": "image/png"}
    assert not can_reuse_icon(original, thumbnail)
    cached_thumbnail = {**original, "embedded_width": 224, "embedded_height": 140}
    assert can_reuse_icon(cached_thumbnail, thumbnail)
    assert not can_reuse_icon(cached_thumbnail, {**thumbnail, "sha1": "b" * 40})


def test_loadout_database_is_chinese_traceable_and_complete() -> None:
    root = Path(__file__).resolve().parent.parent
    data = json.loads((root / "loadout_data.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 2 and data["language"] == "zh-CN"
    assert data["catalog_updated_at"] == "2026-10-21"
    assert len(data["items"]) == 221
    assert data["translation_policy"]["community_translation_count"] == 2
    assert {source["revision"] for source in data["sources"]} >= {
        "14373",
        "9248",
        "139355",
        "136929",
        "138203",
    }

    ids = {item["id"] for item in data["items"]}
    names = {item["name"] for item in data["items"]}
    assert len(ids) == len(names) == len(data["items"])
    for item in data["items"]:
        assert item["name"] == item["name_zh"]
        assert re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", item["name"])
        assert item["name_en"] and item["wiki_en_page"].startswith("https://helldivers.wiki.gg/wiki/")
        assert re.fullmatch(r"[0-9a-f]{40}", item["icon_sha1"])
        assert item["icon_source"].startswith((
            "https://helldivers.wiki.gg/zh/wiki/File:",
            "https://helldivers.wiki.gg/wiki/File:",
        ))

    community = {
        item["name_en"]: item["name"]
        for item in data["items"]
        if item["translation_source"] == "community_translation"
    }
    assert community == {
        "Surplus EAT Allocation": "额外消耗性反坦克武器配额",
        "Integrated Extinguishers": "集成灭火器",
    }
    assert sorted(community.values()) == sorted(data["translation_policy"]["community_translations"])


def test_loadout_icons_cover_every_item_and_match_recorded_digests() -> None:
    root = Path(__file__).resolve().parent.parent
    data = json.loads((root / "loadout_data.json").read_text(encoding="utf-8"))
    icon_payload = json.loads((root / "loadout_icons.json").read_text(encoding="utf-8"))
    pool = load_loadout_pool()
    icons = load_loadout_icons()
    names = {name for names in pool.values() for name in names}
    assert icon_payload["schema_version"] == 2
    assert len(names) == len(icons) == len(icon_payload["files"]) == 221
    assert icon_payload["catalog_updated_at"] == data["catalog_updated_at"]
    assert set(icons) == set(icon_payload["files"]) == names
    assert {item["name"] for item in data["items"]} == names

    for name, uri in icons.items():
        header, encoded = uri.split(",", 1)
        assert header.startswith("data:image/") and header.endswith(";base64")
        payload = base64.b64decode(encoded, validate=True)
        metadata = icon_payload["files"][name]
        assert hashlib.sha256(payload).hexdigest() == metadata["embedded_sha256"]
        assert re.fullmatch(r"[0-9a-f]{40}", metadata["source_sha1"])
        assert metadata["query_url"] == next(item["icon_source"] for item in data["items"] if item["name"] == name)
        if metadata.get("retrieval_method"):
            assert metadata["uploader"] == "Tech Support Squid"
            assert hashlib.sha1(payload).hexdigest() == metadata["source_sha1"]
        if metadata["mime"] == "image/png":
            assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        elif metadata["mime"] == "image/svg+xml":
            assert b"<svg" in payload[:1000]
        else:
            raise AssertionError(f"unexpected icon MIME for {name}: {metadata['mime']}")


def test_real_icon_card_references_nothing_outside_itself() -> None:
    """The shipping icon set must keep the card renderable with allow_network off."""
    page = render_loadout_html(LOADOUT_SAMPLE, icons=load_loadout_icons())
    assert page.count('<img src="data:image/') == len(LOADOUT_SAMPLE)
    # Every src/href is a data URI, so a blackholed network cannot change the card.
    assert not re.search(r'(?:src|href)="(?!data:)', page)


def test_loadout_icons_tolerate_a_missing_file() -> None:
    import plugin as plugin_module

    saved = plugin_module._LOADOUT_ICONS_CACHE
    plugin_module._LOADOUT_ICONS_CACHE = None
    try:
        assert plugin_module.load_loadout_icons("does-not-exist.json") == {}
    finally:
        plugin_module._LOADOUT_ICONS_CACHE = saved


def test_loadout_command_sends_an_image() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)
        rendered: list[str] = []
        sent: list[str] = []

        class FakeRender:
            async def html2png(self, html: str, **kwargs: object) -> dict:
                rendered.append(html)
                return {"image_base64": "AAAA", "mime_type": "image/png"}

        class FakeSend:
            async def image(self, image_data: str, stream_id: str) -> bool:
                sent.append(image_data)
                return True

        class Ctx:
            render = FakeRender()
            send = FakeSend()

        attach_ctx(plugin, Ctx())
        ok, _, _ = await plugin.handle_command(text="/helldivers 配装", stream_id="s", group_id="100")
        assert ok
        assert sent == ["AAAA"] and len(rendered) == 1
        assert "绝地潜兵 2：民主帮你选择" in rendered[0]
        # The shipped icon set is wired in, so the card carries real artwork.
        assert '<img src="data:image/' in rendered[0]
        assert replies == []  # no text fallback once the image went out

    asyncio.run(scenario())


def test_loadout_command_falls_back_to_text_when_rendering_fails() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)

        class BrokenRender:
            async def html2png(self, html: str, **kwargs: object) -> dict:
                raise RuntimeError("no browser available")

        class Ctx:
            render = BrokenRender()

        attach_ctx(plugin, Ctx())
        ok, _, _ = await plugin.handle_command(text="/helldivers loadout", stream_id="s", group_id="100")
        assert ok and replies
        assert replies[-1].startswith("【绝地潜兵 2：民主帮你选择·随机配装】")
        assert "主武器：" in replies[-1] and "战略配备：" in replies[-1]
        # The host's reason must travel with the fallback, not vanish into a log.
        assert "no browser available" in replies[-1]
        assert "配装图生成失败" in replies[-1]

    asyncio.run(scenario())


def test_loadout_fallback_surfaces_a_rejected_render_payload() -> None:
    """MaiBot answers a failed render with success=False instead of raising."""

    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)

        class RejectingRender:
            async def html2png(self, html: str, **kwargs: object) -> dict:
                return {"success": False, "error": "插件运行时浏览器渲染能力已禁用"}

        class Ctx:
            render = RejectingRender()

        attach_ctx(plugin, Ctx())
        await plugin.handle_command(text="/helldivers loadout", stream_id="s", group_id="100")
        assert "插件运行时浏览器渲染能力已禁用" in replies[-1]
        assert plugin._last_render_error == "插件运行时浏览器渲染能力已禁用"

    asyncio.run(scenario())


def test_loadout_fallback_surfaces_a_rejected_image_send() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)

        class GoodRender:
            async def html2png(self, html: str, **kwargs: object) -> dict:
                return {"image_base64": "AAAA", "mime_type": "image/png"}

        class RefusingSend:
            async def image(self, image_data: str, stream_id: str) -> bool:
                return False

        class Ctx:
            render = GoodRender()
            send = RefusingSend()

        attach_ctx(plugin, Ctx())
        await plugin.handle_command(text="/helldivers loadout", stream_id="s", group_id="100")
        assert "发送图片返回 False" in replies[-1]

    asyncio.run(scenario())


def test_card_stylesheets_are_brace_balanced() -> None:
    """A stray ``}}`` in a non-f-string silently swallows the next CSS rule."""
    pages = (("diag", DIAG_HTML), ("card", render_loadout_html(LOADOUT_SAMPLE)))
    for name, page in pages:
        css = page.split("<style>")[1].split("</style>")[0]
        assert css.count("{") == css.count("}"), f"{name} 的 CSS 花括号不平衡"
        assert page.count("<style>") == 1 and page.count("</style>") == 1


def command_metadata() -> dict:
    """``@Command`` metadata, shape-agnostic across the real SDK and the stub."""
    info = getattr(DemocracyChoosesPlugin.handle_command, "__maibot_component_info__", None)
    if info is None:
        return {}
    return dict(getattr(info, "metadata", info) or {})


def test_command_timeout_covers_the_render_budget() -> None:
    """A cold browser launch needs more than the host's default 60 s budget."""
    assert RENDER_RPC_TIMEOUT_MS > 60_000  # MaiBot's DEFAULT_COMPONENT_RPC_TIMEOUT_MS
    assert COMMAND_RPC_TIMEOUT_MS > RENDER_RPC_TIMEOUT_MS
    metadata = command_metadata()
    if metadata:  # the stub also records it, so this is not vacuous
        assert metadata["timeout_ms"] == COMMAND_RPC_TIMEOUT_MS


def test_render_raises_the_rpc_timeout_above_the_host_cap() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)
        calls: list[tuple[str, int, dict]] = []

        class Ctx:
            async def call_capability(
                self, capability: str, timeout_ms: int | None = None, **kwargs: object
            ) -> dict:
                calls.append((capability, int(timeout_ms or 0), dict(kwargs)))
                return {"image_base64": "AAAA", "mime_type": "image/png"}

        attach_ctx(plugin, Ctx())
        ok, _, _ = await plugin.handle_command(text="/helldivers loadout", stream_id="s", user_id="u1", group_id="100")
        assert ok
        assert len(calls) == 1
        capability, timeout_ms, args = calls[0]
        assert capability == "render.html2png"
        assert timeout_ms == RENDER_RPC_TIMEOUT_MS
        # timeout_ms is an RPC argument, never a capability argument.
        assert "timeout_ms" not in args
        assert args["selector"] == "body" and args["full_page"] is True
        assert args["viewport"] == {"width": LOADOUT_CARD_WIDTH, "height": LOADOUT_CARD_HEIGHT}
        assert args["render_timeout_ms"] == RENDER_RPC_TIMEOUT_MS
        assert args["allow_network"] is False
        assert args["html"].startswith("<!DOCTYPE html>")

    asyncio.run(scenario())


def test_render_falls_back_to_the_typed_proxy_without_call_capability() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)
        seen: list[dict] = []

        class Render:
            async def html2png(self, html: str, **kwargs: object) -> dict:
                seen.append(dict(kwargs))
                return {"image_base64": "AAAA"}

        class Send:
            async def image(self, image_data: str, stream_id: str) -> bool:
                return True

        class Ctx:
            render = Render()
            send = Send()

        attach_ctx(plugin, Ctx())
        ok, _, _ = await plugin.handle_command(text="/helldivers loadout", stream_id="s", group_id="100")
        assert ok and len(seen) == 1
        assert seen[0] == {
            "selector": "body",
            "viewport": {"width": LOADOUT_CARD_WIDTH, "height": LOADOUT_CARD_HEIGHT},
            "device_scale_factor": 1.0,
            "full_page": True,
            "render_timeout_ms": RENDER_RPC_TIMEOUT_MS,
            "allow_network": False,
        }

    asyncio.run(scenario())


def test_diag_explains_a_render_timeout() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)

        class Ctx:
            async def call_capability(
                self, capability: str, timeout_ms: int | None = None, **kwargs: object
            ) -> dict:
                raise RuntimeError(f"[E_TIMEOUT] 请求 cap.call 超时 ({timeout_ms}ms)")

        attach_ctx(plugin, Ctx())
        ok, _, _ = await plugin.handle_command(text="/helldivers diag", stream_id="s", is_local_operator=True, group_id="100")
        assert ok is False
        text = replies[-1]
        assert "渲染超时" in text
        assert str(RENDER_RPC_TIMEOUT_MS // 1000) in text
        assert "Playwright" in text and "Chromium" in text
        assert "E_TIMEOUT" in text  # the host's own words are still shown

    asyncio.run(scenario())


def test_diag_reports_the_render_failure_and_how_to_fix_it() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, _rendered, sent = loadout_plugin(replies)

        class BrokenRender:
            async def html2png(self, html: str, **kwargs: object) -> dict:
                return {"success": False, "error": "当前环境未安装 Python Playwright"}

        ctx_obj = plugin.ctx


        ctx_obj.render = BrokenRender()  # type: ignore[assignment]
        ok, _, _ = await plugin.handle_command(text="/helldivers 自检", stream_id="s", is_local_operator=True, group_id="100")
        assert ok is False
        text = replies[-1]
        assert text.startswith("【绝地潜兵 2：民主帮你选择·自检】")
        assert "配装数据：" in text and "装备图标：" in text and "重抽时间窗：" in text
        assert "浏览器渲染：失败" in text
        assert "当前环境未安装 Python Playwright" in text
        assert "plugin_runtime.render.enabled" in text
        assert sent == []  # nothing was sent as an image

    asyncio.run(scenario())


def test_diag_sends_a_real_test_image_when_the_pipeline_works() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, rendered, sent = loadout_plugin(replies)
        ok, _, _ = await plugin.handle_command(text="/helldivers diag", stream_id="s", is_local_operator=True, group_id="100")
        assert ok
        assert len(rendered) == 1 and "渲染自检 OK" in rendered[0]
        assert sent == ["AAAA"]  # exactly one image, not two
        text = replies[-1]
        assert "浏览器渲染：成功" in text and "图片发送：成功" in text
        assert plugin._last_render_error == ""

    asyncio.run(scenario())


def test_status_surfaces_the_last_image_failure() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)
        plugin._last_render_error = "插件运行时浏览器渲染能力已禁用"
        await plugin.handle_command(text="/helldivers status", stream_id="s", group_id="100")
        assert "配装出图异常：插件运行时浏览器渲染能力已禁用" in replies[-1]

    asyncio.run(scenario())


def test_format_loadout_numbers_match_the_card_badges() -> None:
    text = format_loadout(LOADOUT_SAMPLE)
    assert "1 主武器：AR-23 解放者" in text
    assert "4 强化资源：UAV侦察强化" in text
    assert "5 战略配备：MG-43 机枪" in text
    assert "8 战略配备：SH-20 防弹护盾背包" in text


def loadout_plugin(replies: list[str]) -> tuple[DemocracyChoosesPlugin, list[str], list[str]]:
    """Plugin wired for loadout commands, with rendered HTML and sent images captured."""
    plugin = command_plugin(replies)
    rendered: list[str] = []
    sent: list[str] = []

    class FakeRender:
        async def html2png(self, html: str, **kwargs: object) -> dict:
            rendered.append(html)
            return {"image_base64": "AAAA", "mime_type": "image/png"}

    class FakeSend:
        async def image(self, image_data: str, stream_id: str) -> bool:
            sent.append(image_data)
            return True

    class Ctx:
        render = FakeRender()
        send = FakeSend()

    attach_ctx(plugin, Ctx())
    return plugin, rendered, sent


def attach_ctx(plugin: DemocracyChoosesPlugin, ctx: object) -> None:
    """Inject a fake context.

    The stub ``MaiBotPlugin`` accepts ``plugin.ctx = ...``; the real SDK exposes
    ``ctx`` as a read-only property and injects it through ``_set_context``.
    """
    setter = getattr(plugin, "_set_context", None)
    if callable(setter):
        setter(ctx)
        return
    plugin.ctx = ctx  # type: ignore[assignment]


def session_slots(plugin: DemocracyChoosesPlugin, scope: str = "s|u1") -> dict[str, str]:
    return dict(plugin._loadout_sessions[scope][0])


def age_session(plugin: DemocracyChoosesPlugin, seconds: float, scope: str = "s|u1") -> None:
    loadout, motto, stamp = plugin._loadout_sessions[scope]
    plugin._loadout_sessions[scope] = (loadout, motto, stamp - seconds)


def test_loadout_reroll_redraws_only_the_requested_slot() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, _rendered, sent = loadout_plugin(replies)
        ok, _, _ = await plugin.handle_command(text="/helldivers loadout", stream_id="s", user_id="u1", group_id="100")
        assert ok and len(sent) == 1
        before = session_slots(plugin)

        # The Chinese alias path must work too.
        ok, _, _ = await plugin.handle_command(text="/helldivers 配装 3", stream_id="s", user_id="u1", group_id="100")
        assert ok
        after = session_slots(plugin)
        assert {key for key in after if after[key] != before[key]} == {"grenade"}
        assert after["grenade"] != before["grenade"]
        assert len(sent) == 2  # the reroll comes back as an image as well
        assert replies == []

    asyncio.run(scenario())


def test_loadout_reroll_keeps_the_four_stratagems_distinct() -> None:
    async def scenario() -> None:
        plugin, _rendered, _sent = loadout_plugin([])
        await plugin.handle_command(text="/helldivers loadout", stream_id="s", user_id="u1", group_id="100")
        before = session_slots(plugin)
        previous = {before[f"stratagem_{index}"] for index in range(LOADOUT_STRATAGEM_COUNT)}

        ok, _, _ = await plugin.handle_command(text="/helldivers loadout 7", stream_id="s", user_id="u1", group_id="100")
        assert ok
        after = session_slots(plugin)
        picked = [after[f"stratagem_{index}"] for index in range(LOADOUT_STRATAGEM_COUNT)]
        assert len(set(picked)) == LOADOUT_STRATAGEM_COUNT
        # Slot 7 is stratagem_2 alone, and it must be a different stratagem.
        assert after["stratagem_2"] not in previous
        assert {key for key in after if after[key] != before[key]} == {"stratagem_2"}

    asyncio.run(scenario())


def test_loadout_reroll_stops_working_after_the_window() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, _rendered, sent = loadout_plugin(replies)
        await plugin.handle_command(text="/helldivers loadout", stream_id="s", user_id="u1", group_id="100")
        age_session(plugin, LOADOUT_REROLL_TTL_SECONDS + 1)

        ok, _, _ = await plugin.handle_command(text="/helldivers loadout 3", stream_id="s", user_id="u1", group_id="100")
        assert ok is False
        assert "没有可重抽的配装" in replies[-1] and str(LOADOUT_REROLL_TTL_SECONDS) in replies[-1]
        assert len(sent) == 1  # nothing new was drawn
        assert "s|u1" not in plugin._loadout_sessions  # expired sessions are dropped

    asyncio.run(scenario())


def test_loadout_reroll_window_slides_and_accepts_chinese_numerals() -> None:
    async def scenario() -> None:
        plugin, _rendered, sent = loadout_plugin([])
        await plugin.handle_command(text="/helldivers loadout", stream_id="s", user_id="u1", group_id="100")
        # Still inside the window, but only just.
        age_session(plugin, LOADOUT_REROLL_TTL_SECONDS - 5)

        ok, _, _ = await plugin.handle_command(text="/helldivers loadout 三", stream_id="s", user_id="u1", group_id="100")
        assert ok and len(sent) == 2
        _loadout, _motto, stamp = plugin._loadout_sessions["s|u1"]
        # A reroll restarts the countdown, so a chain of rerolls keeps working.
        assert time.monotonic() - stamp < 5

    asyncio.run(scenario())


def test_loadout_reroll_rejects_bad_numbers_and_never_draws_a_fresh_loadout() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, _rendered, sent = loadout_plugin(replies)
        await plugin.handle_command(text="/helldivers loadout", stream_id="s", user_id="u1", group_id="100")
        before = session_slots(plugin)

        for bad in ("0", "9", "abc"):
            replies.clear()
            ok, _, _ = await plugin.handle_command(text=f"/helldivers loadout {bad}", stream_id="s", user_id="u1", group_id="100")
            assert ok is False, bad
            assert "序号需要在 1-8 之间" in replies[-1]
        assert len(sent) == 1
        assert session_slots(plugin) == before  # a rejected reroll leaves the draw alone

    asyncio.run(scenario())


def test_loadout_reroll_is_scoped_to_the_user_who_drew_it() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, _rendered, sent = loadout_plugin(replies)
        await plugin.handle_command(text="/helldivers loadout", stream_id="s", user_id="u1", group_id="100")

        ok, _, _ = await plugin.handle_command(text="/helldivers loadout 3", stream_id="s", user_id="u2", group_id="100")
        assert ok is False and "没有可重抽的配装" in replies[-1]
        assert len(sent) == 1
        # A different chat is a different session as well.
        ok, _, _ = await plugin.handle_command(text="/helldivers loadout 3", stream_id="other", user_id="u1", group_id="100")
        assert ok is False and len(sent) == 1

    asyncio.run(scenario())


def test_loadout_without_a_previous_draw_asks_to_roll_first() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, _rendered, sent = loadout_plugin(replies)
        ok, _, _ = await plugin.handle_command(text="/helldivers loadout 5", stream_id="s", user_id="u1", group_id="100")
        assert ok is False and "请先发 /helldivers loadout" in replies[-1]
        assert sent == []

    asyncio.run(scenario())


def test_help_stays_in_sync_with_the_command_surface() -> None:
    """Guards the drift that left ``loadout`` out of the topic list."""
    plugin = command_plugin([])
    hint = usage_hint()
    for action in sorted(COMMAND_ACTIONS):
        assert action in HELP_TOPICS, f"{action} 没有帮助主题"
        assert f"/helldivers {action}" in hint, f"{action} 不在用法总览里"
    # Every topic must appear in the "可用的主题" line of ``help help``.
    listed = HELP_TOPICS["help"]
    for topic in sorted(HELP_TOPICS):
        assert topic in listed, f"{topic} 未列在 help 主题清单里"
    for topic in HELP_TOPICS:
        assert "中文写法" in plugin._help_text(topic), f"{topic} 主题没写中文写法"
    # Status output wording must match what the command actually prints.
    assert "重抽" in plugin._help_text("status")


def test_help_lookup_resolves_topics_and_aliases() -> None:
    plugin = command_plugin([])
    for topic in HELP_TOPICS:
        assert plugin._help_text(topic).startswith("【/helldivers")
    assert plugin._help_text("配装") == plugin._help_text("loadout")
    assert plugin._help_text("状态") == plugin._help_text("status")
    assert plugin._help_text("banana").startswith("没有「banana」这个主题")
    assert plugin._help_text("") == usage_hint()


def test_help_renders_the_configured_tunables_instead_of_the_defaults() -> None:
    plugin = command_plugin([])
    plugin._cfg = {"allowed_groups": ["100"],
        "loadout_reroll_seconds": 42,
    }
    assert "42 秒" in plugin._help_text("loadout")
    usage = plugin._help_text("")
    assert "42 秒" in usage
    # A bad hand-edited value falls back to the default instead of raising.
    plugin._cfg["loadout_reroll_seconds"] = "abc"
    assert str(LOADOUT_REROLL_TTL_SECONDS) in plugin._help_text("loadout")


MANIFEST_PATH = Path(__file__).resolve().parent.parent / "_manifest.json"


PLUGIN_PATH = Path(__file__).resolve().parent.parent / "plugin.py"


PLUGIN_TYPES = frozenset(
    {"adapter", "tool", "provider", "management", "data", "media", "game", "integration", "extension", "other"}
)


CAPABILITIES_IN_USE = frozenset({"send.text", "send.image", "render.html2png"})


SEMVER = r"\d+\.\d+\.\d+"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_matches_the_documented_schema() -> None:
    """Host 的 ManifestValidator 是严格模式：字段写错会直接被拒绝加载。"""
    manifest = load_manifest()
    assert manifest["manifest_version"] == 2
    assert re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", manifest["id"]), manifest["id"]
    assert re.fullmatch(SEMVER, manifest["version"]), manifest["version"]
    for key in ("name", "description", "license"):
        assert isinstance(manifest[key], str) and manifest[key].strip(), key

    author = manifest["author"]
    assert author["name"].strip()
    assert author["url"].startswith(("http://", "https://")), "author.url 必填且必须是 URL"

    assert manifest["urls"]["repository"].startswith(("http://", "https://"))
    for key, value in manifest["urls"].items():
        assert value.startswith(("http://", "https://")), key

    for key in ("host_application", "sdk"):
        window = manifest[key]
        assert re.fullmatch(SEMVER, window["min_version"]), (key, window)
        assert re.fullmatch(SEMVER, window["max_version"]), (key, window)
        assert tuple(map(int, window["min_version"].split("."))) <= tuple(map(int, window["max_version"].split("."))), key

    assert manifest["plugin_type"] in PLUGIN_TYPES, manifest["plugin_type"]
    assert manifest["capabilities"] and all(isinstance(item, str) and item.strip() for item in manifest["capabilities"])
    assert len(set(manifest["capabilities"])) == len(manifest["capabilities"])

    i18n = manifest["i18n"]
    assert i18n["supported_locales"], "supported_locales 非空时 default_locale 必须在其中"
    assert i18n["default_locale"] in i18n["supported_locales"]


def test_sdk_minimum_is_consistent_across_release_files() -> None:
    minimum = load_manifest()["sdk"]["min_version"]
    root = MANIFEST_PATH.parent
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert f"maibot-plugin-sdk>={minimum},<3.0" in requirements
    assert f"`>= {minimum}, < 3.0.0`" in readme


def test_manifest_uses_the_repository_owners_identity() -> None:
    """Publication metadata must not drift back to a previous or project-name signature."""
    manifest = load_manifest()
    assert manifest["id"] == "github.touristh.helldivers2-democracy-chooses"
    assert manifest["author"] == {"name": "TouristH", "url": "https://github.com/TouristH"}
    expected = "https://github.com/TouristH/Helldivers2DemocracyChooses"
    assert manifest["urls"]["repository"] == expected
    assert manifest["urls"]["homepage"] == expected
    assert manifest["urls"]["documentation"] == f"{expected}/blob/main/README.md"
    assert manifest["urls"]["issues"] == f"{expected}/issues"


def test_license_and_third_party_notices_are_published() -> None:
    root = MANIFEST_PATH.parent
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    notices = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert load_manifest()["license"] == "MIT"
    assert "MIT License" in license_text and "Copyright (c) 2026 TouristH" in license_text
    assert "Xenfo-LC/Helldivers-2-Random-Loadout-Generator-CN" in notices
    assert "Erlend Dahl" in notices and "Xenfo" in notices
    assert "did not contain a standalone open-source license" in notices
    for revision in ("14373", "9248", "139355", "136929", "138203"):
        assert f"`{revision}`" in notices
    assert "CC BY-SA 4.0" in notices and "CC BY-NC-SA 4.0" in notices
    assert "creativecommons.org/licenses/by-sa/4.0" in notices
    assert "creativecommons.org/licenses/by-nc-sa/4.0" in notices
    assert "loadout_data.json" in notices and "221" in notices
    assert "Tech Support Squid" in " ".join(notices.split())
    assert "no equipment record or embedded icon" in notices
    contributors = (root / "CONTRIBUTORS.md").read_text(encoding="utf-8")
    assert "TouristH" in contributors and "OpenAI Codex" in contributors


def test_manifest_dependencies_are_well_formed() -> None:
    manifest = load_manifest()
    seen: set[str] = set()
    for dependency in manifest["dependencies"]:
        assert dependency["type"] in {"plugin", "python_package"}, dependency
        assert dependency["version_spec"].strip(), dependency
        key = dependency.get("id") if dependency["type"] == "plugin" else dependency["name"]
        assert key and key != manifest["id"], "不允许自依赖"
        assert key not in seen, f"不允许重复声明依赖：{key}"
        seen.add(key)
        if dependency["type"] == "python_package":
            assert re.fullmatch(r"[A-Za-z0-9._-]+", dependency["name"]), dependency["name"]
        else:
            assert re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", dependency["id"]), dependency["id"]


def test_manifest_declares_the_python_package_the_host_must_install() -> None:
    """插件自身的 requirements.txt 不被宿主读取；自动安装只认这里的 python_package。"""
    packages = {
        item["name"]: item for item in load_manifest()["dependencies"] if item["type"] == "python_package"
    }
    assert "playwright" in packages, "宿主渲染能力需要 playwright，缺失时渲染必定失败"
    # 约束必须与主程序（playwright>=1.54.0）有交集，否则插件会被拒绝加载。
    assert packages["playwright"]["version_spec"].startswith(">=")


def test_manifest_declares_every_capability_the_plugin_uses() -> None:
    declared = set(load_manifest()["capabilities"])
    assert CAPABILITIES_IN_USE <= declared, f"未声明的能力：{CAPABILITIES_IN_USE - declared}"
    # The raw capability name used by the render call must be declared too.
    source = PLUGIN_PATH.read_text(encoding="utf-8")
    for capability in re.findall(r'call_capability\(\s*"([^"]+)"', source):
        assert capability in declared, f"call_capability 用了未声明的能力：{capability}"


def test_manifest_does_not_claim_locales_it_does_not_ship() -> None:
    """``en-US`` was declared while every user-facing string is Chinese."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    i18n = manifest["i18n"]
    locales_dir = MANIFEST_PATH.parent / str(i18n.get("locales_path") or "i18n")
    shipped = {path.stem for path in locales_dir.glob("*.json")} if locales_dir.exists() else set()
    allowed = shipped | {i18n["default_locale"]}
    claimed = set(i18n.get("supported_locales", []))
    assert claimed <= allowed, (
        f"声明了却没有语言文件的语言：{sorted(claimed - allowed)}（要么补 i18n/<locale>.json，要么从 supported_locales 去掉）"
    )


def test_requirements_txt_supports_manual_install_when_auto_install_fails() -> None:
    """requirements.txt 同时列出宿主侧依赖，供用户手动安装。

    Host 自动安装（manifest dependencies）可能因网络等原因失败；requirements.txt
    里列出的 python_package 必须与 manifest 声明保持一致，方便用户
    ``pip install -r requirements.txt`` 兜底。
    """
    text = (MANIFEST_PATH.parent / "requirements.txt").read_text(encoding="utf-8")
    assert "maibot-plugin-sdk" in text
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    packages = [d for d in manifest["dependencies"] if d.get("type") == "python_package"]
    assert packages, "manifest 至少声明一个 python_package"
    for dep in packages:
        pin = f"{dep['name']}{dep['version_spec']}"
        assert pin in text.replace(" ", ""), (
            f"manifest 声明的 {pin} 没有同步写进 requirements.txt，手动安装会漏装"
        )


def config_field_names() -> set[str]:
    """``PluginSection`` field names, with or without pydantic behind it."""
    fields = getattr(PluginSection, "model_fields", None)
    if isinstance(fields, dict):
        return set(fields)
    return {name for name in vars(PluginSection) if not name.startswith("_")}


def config_keys_read_by_code() -> set[str]:
    source = PLUGIN_PATH.read_text(encoding="utf-8")
    keys = set(re.findall(r'_cfg\.get\(\s*"([a-z_0-9]+)"', source))
    keys |= set(re.findall(r'_cfg_int\(\s*"([a-z_0-9]+)"', source))
    keys |= set(re.findall(r'_cfg_bool\(\s*"([a-z_0-9]+)"', source))
    keys |= set(re.findall(r'_cfg_id_list\(\s*"([a-z_0-9]+)"', source))
    return keys


def test_config_model_declares_every_key_the_code_reads() -> None:
    """Guards the old defect: keys were read but never exposed, so nobody could set them."""
    missing = sorted(config_keys_read_by_code() - config_field_names())
    assert not missing, f"代码在读但模型里没有的配置项（WebUI 配不出来）：{missing}"


def test_every_config_field_is_actually_used() -> None:
    """Guards the opposite drift: knobs that exist in the WebUI but change nothing."""
    # MaiBot's Runner uses this field before the plugin is activated.
    unused = sorted(config_field_names() - config_keys_read_by_code() - {"config_version"})
    assert not unused, f"声明了但代码从不读取的配置项：{unused}"


def test_example_config_documents_every_field() -> None:
    text = (MANIFEST_PATH.parent / "config.example.toml").read_text(encoding="utf-8")
    missing = sorted(name for name in config_field_names() if f"{name} =" not in text)
    assert not missing, f"config.example.toml 缺少这些配置项：{missing}"


def test_example_config_validates_against_the_model() -> None:
    """The shipped example must parse and contain no keys the model rejects."""
    import tomllib

    with (MANIFEST_PATH.parent / "config.example.toml").open("rb") as handle:
        example = tomllib.load(handle)
    validated = PluginConfig.model_validate(example).model_dump()["plugin"]
    unknown = sorted(set(example["plugin"]) - set(validated))
    assert not unknown, f"config.example.toml 写了模型不认识的键：{unknown}"


def test_runner_defaults_and_example_supply_the_config_version() -> None:
    import tomllib

    defaults = DemocracyChoosesPlugin().get_default_config()
    with (MANIFEST_PATH.parent / "config.example.toml").open("rb") as handle:
        example = tomllib.load(handle)

    assert defaults["plugin"].get("config_version") == "1.0.0"
    assert example["plugin"].get("config_version") == "1.0.0"


def test_config_fields_carry_webui_metadata() -> None:
    fields = getattr(PluginSection, "model_fields", None)
    if not isinstance(fields, dict):
        import pytest

        pytest.skip("未安装 maibot-plugin-sdk，配置模型退化为普通类属性")
    groups = set()
    for name, info in fields.items():
        assert (info.description or "").strip(), f"{name} 缺少 description"
        extra = info.json_schema_extra or {}
        assert str(extra.get("label") or "").strip(), f"{name} 缺少 WebUI label"
        assert extra.get("group"), f"{name} 缺少 WebUI 分组"
        groups.add(extra["group"])
    assert groups == {"基础", "权限", "随机配装"}, groups


def test_group_allowlist_is_editable_in_generated_webui_form() -> None:
    from maibot_sdk.config import generate_plugin_config_schema

    schema = generate_plugin_config_schema(PluginConfig)
    fields = schema["sections"]["plugin"]["fields"]
    visible_fields = {name for name, field in fields.items() if not field.get("hidden")}
    assert "allowed_groups" in visible_fields
    assert fields["allowed_groups"]["ui_type"] == "list"
    assert fields["allowed_groups"]["item_type"] == "string"
    assert "config_version" not in visible_fields
    assert {"admin_users", "command_blacklist", "loadout_reroll_seconds"} <= visible_fields
    config = PluginConfig.model_validate({"plugin": {"allowed_groups": ["100"]}})
    assert config.plugin.allowed_groups == ["100"]


def test_blacklist_webui_schema_uses_editable_rule_rows() -> None:
    schema = DemocracyChoosesPlugin().get_webui_config_schema()
    blacklist = schema["sections"]["plugin"]["fields"]["command_blacklist"]

    assert blacklist["ui_type"] == "list"
    assert blacklist["item_type"] == "object"
    assert blacklist["default"] == []
    assert set(blacklist["item_fields"]["action"]["choices"]) == {"*"} | FUNCTIONAL_ACTIONS
    assert blacklist["item_fields"]["user_id"]["type"] == "string"


def test_config_numeric_fields_declare_sane_bounds() -> None:
    fields = getattr(PluginSection, "model_fields", None)
    if not isinstance(fields, dict):
        import pytest

        pytest.skip("未安装 maibot-plugin-sdk，配置模型退化为普通类属性")
    checked = 0
    for name, info in fields.items():
        if info.annotation not in {int, float}:
            continue
        bounds: dict[str, float] = {}
        for metadata in info.metadata:
            if getattr(metadata, "ge", None) is not None:
                bounds["ge"] = metadata.ge
            if getattr(metadata, "le", None) is not None:
                bounds["le"] = metadata.le
        assert "ge" in bounds and "le" in bounds, f"{name} 数值项应同时声明 ge/le"
        assert bounds["ge"] <= bounds["le"], name
        checked += 1
    assert checked == 1


def test_config_defaults_are_validated_by_the_real_model() -> None:
    """With the SDK present, the declared defaults must pass pydantic validation."""
    fields = getattr(PluginSection, "model_fields", None)
    if not isinstance(fields, dict):
        import pytest

        pytest.skip("未安装 maibot-plugin-sdk，配置模型退化为普通类属性")
    instance = PluginSection()
    dumped = instance.model_dump(mode="python")
    assert set(dumped) == config_field_names()
    # Bounds and defaults must agree with what the code falls back to.
    assert instance.loadout_reroll_seconds == LOADOUT_REROLL_TTL_SECONDS


def test_card_icon_attribute_is_escaped() -> None:
    """The icon lands in an HTML attribute, so a hand-edited file cannot break out."""
    hostile = 'data:image/png;base64,x" onerror="alert(1)'
    html_text = render_loadout_html(
        {"primary": "AR-23", "secondary": "", "grenade": "", "booster": ""},
        icons={"AR-23": hostile},
    )
    assert '" onerror="' not in html_text, "图标属性里的引号必须被转义"
    assert "&quot;" in html_text


def test_every_command_is_exactly_one_of_functional_or_admin() -> None:
    """The two permission classes must partition the command surface."""
    assert not (FUNCTIONAL_ACTIONS & ADMIN_ACTIONS), "同一指令不能既是功能又是管理"
    assert FUNCTIONAL_ACTIONS | ADMIN_ACTIONS == COMMAND_ACTIONS, (
        f"未分类的指令：{sorted(COMMAND_ACTIONS - FUNCTIONAL_ACTIONS - ADMIN_ACTIONS)}"
    )
    assert ADMIN_ACTIONS, "至少要有一个管理指令"


def test_functional_commands_are_open_to_anyone() -> None:
    plugin = command_plugin([])
    for action in sorted(FUNCTIONAL_ACTIONS):
        assert plugin._command_permission({"user_id": "100"}, action) == "", f"{action} 不该拦普通用户"


def test_management_commands_need_the_whitelist() -> None:
    plugin = command_plugin([])
    plugin._cfg = {"allowed_groups": ["100"], "admin_users": ["900"]}
    for action in sorted(ADMIN_ACTIONS):
        assert plugin._command_permission({"user_id": "100"}, action), f"{action} 应拦住普通用户"
        assert plugin._command_permission({"user_id": "900"}, action) == "", f"{action} 应放行管理员"
        assert plugin._command_permission({"user_id": "100", "is_local_operator": True}, action) == ""


def test_admin_whitelist_accepts_unquoted_numbers() -> None:
    """``admin_users = [123456789]`` in TOML is an integer list, not a string list."""
    section = PluginConfig.model_validate({"plugin": {"admin_users": [123456789]}}).plugin
    assert section.admin_users == ["123456789"]


def test_blacklist_blocks_functional_commands_only() -> None:
    plugin = command_plugin([])
    plugin._cfg = {"allowed_groups": ["100"], "command_blacklist": {"*": ["800"], "loadout": ["700"]}}
    # Globally blocked.
    for action in sorted(FUNCTIONAL_ACTIONS):
        assert plugin._command_permission({"user_id": "800"}, action), f"{action} 应被全局黑名单拦住"
    # Blocked for exactly one command.
    assert plugin._command_permission({"user_id": "700"}, "loadout")
    for action in sorted(FUNCTIONAL_ACTIONS - {"loadout"}):
        assert plugin._command_permission({"user_id": "700"}, action) == "", f"{action} 不该受影响"
    # Anyone not listed is unaffected.
    assert plugin._command_permission({"user_id": "100"}, "loadout") == ""


def test_blacklist_keys_accept_action_aliases() -> None:
    plugin = command_plugin([])
    for key in ("配装", "lo", "loadout"):
        plugin._cfg = {"allowed_groups": ["100"], "command_blacklist": {key: ["700"]}}
        assert plugin._command_permission({"user_id": "700"}, "loadout"), f"别名 {key} 没生效"


def test_legacy_blacklist_normalizes_aliases_and_empty_rule_list_unblocks_users() -> None:
    plugin = command_plugin([])
    legacy = {
        "plugin": {
            "config_version": "1.0.0",
            "allowed_groups": ["100"],
            "command_blacklist": {"all": ["900"], "lo": ["700"], "loadout": [700, "800"]},
        }
    }
    normalized, _ = plugin.normalize_plugin_config(legacy)
    config = normalized["plugin"]
    assert config["command_blacklist"] == [
        {"action": "*", "user_id": "900"},
        {"action": "loadout", "user_id": "700"},
        {"action": "loadout", "user_id": "800"},
    ]
    assert config["allowed_groups"] == ["100"]

    asyncio.run(plugin.on_config_update(config_data=normalized))
    assert plugin._command_permission({"user_id": "900"}, "help")
    assert plugin._command_permission({"user_id": "700"}, "loadout")
    assert not plugin._command_permission({"user_id": "700"}, "help")

    config["command_blacklist"] = []
    asyncio.run(plugin.on_config_update(config_data=normalized))
    assert not plugin._command_permission({"user_id": "900"}, "help")
    assert not plugin._command_permission({"user_id": "700"}, "loadout")


def test_admin_whitelist_wins_over_the_blacklist() -> None:
    plugin = command_plugin([])
    plugin._cfg = {"allowed_groups": ["100"], "admin_users": ["900"], "command_blacklist": {"*": ["900"]}}
    for action in sorted(COMMAND_ACTIONS):
        assert plugin._command_permission({"user_id": "900"}, action) == "", f"{action} 应放行管理员"


def test_permission_denial_reaches_the_group_without_side_effects() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)
        ok, why, _ = await plugin.handle_command(
            text="/helldivers diag", stream_id="s", user_id="100", group_id="100"
        )
        assert ok is False and "管理指令" in replies[-1]
        assert why
        # A denied command must not reach the renderer at all.
        assert plugin._last_render_error == ""

        # Blacklisted users get their own message.
        plugin._cfg = {"allowed_groups": ["100"], "command_blacklist": {"*": ["800"]}}
        replies.clear()
        ok, _, _ = await plugin.handle_command(
            text="/helldivers loadout", stream_id="s", user_id="800", group_id="100"
        )
        assert ok is False and "禁止" in replies[-1]
        assert plugin._loadout_sessions == {}

    asyncio.run(scenario())


def test_admin_commands_are_labelled_in_the_help() -> None:
    plugin = command_plugin([])
    assert "管理指令" in plugin._usage_hint()
    for action in sorted(ADMIN_ACTIONS):
        assert "管理指令" in plugin._help_text(action), f"{action} 的帮助没说是管理指令"


def test_blacklist_config_only_names_real_commands() -> None:
    """A typo'd key would silently do nothing, so keep the docs honest."""
    plugin = command_plugin([])
    plugin._cfg = {"allowed_groups": ["100"], "command_blacklist": {"配装": ["1"], "*": ["2"], "不存在的指令": ["3"]}}
    parsed = plugin._command_blacklist()
    assert parsed["loadout"] == {"1"}
    assert parsed["*"] == {"2"}
    # Unknown keys are still carried (harmless) but never match a real action.
    assert "不存在的指令" in parsed
    assert plugin._command_permission({"user_id": "1"}, "loadout")


def test_load_and_config_reload_need_no_database_or_background_tasks(tmp_path: Path) -> None:
    async def scenario() -> None:
        plugin = DemocracyChoosesPlugin()

        class Ctx:
            class paths:
                data_dir = tmp_path / "unused-data"

        attach_ctx(plugin, Ctx())
        tasks_before = asyncio.all_tasks()
        with patch("sqlite3.connect", side_effect=AssertionError("loadout plugin must not open a database")):
            await plugin.on_load()
            await plugin.on_config_update(config_data={"plugin": {"loadout_reroll_seconds": 45}})
            assert plugin._loadout_reroll_seconds() == 45
            assert asyncio.all_tasks() == tasks_before
            await plugin.on_unload()
        assert not (tmp_path / "unused-data").exists()

    asyncio.run(scenario())


def test_allowed_group_can_draw_without_subscription_or_admin_whitelist() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, _rendered, sent = loadout_plugin(replies)
        plugin._cfg = {"allowed_groups": ["100"]}
        ok, _, _ = await plugin.handle_command(
            text="/hd loadout", stream_id="s", user_id="u1", group_id="100"
        )
        assert ok and len(sent) == 1
        assert len(session_slots(plugin)) == 8
        assert not replies

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["subscribe", "unsubscribe", "push", "list", "sub", "推送", "补丁", "wiki"])
def test_retired_news_commands_are_unknown_and_have_no_loadout_side_effects(action: str) -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, rendered, sent = loadout_plugin(replies)
        ok, why, _ = await plugin.handle_command(
            text=f"/helldivers {action}", stream_id="s", user_id="u1", is_local_operator=True, group_id="100"
        )
        assert ok is False and "未知子命令" in why
        assert "未知子命令" in replies[-1]
        assert rendered == [] and sent == [] and plugin._loadout_sessions == {}

    asyncio.run(scenario())


def test_diag_denies_an_unidentified_actor_even_with_an_admin_whitelist() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, rendered, sent = loadout_plugin(replies)
        plugin._cfg = {"allowed_groups": ["100"], "admin_users": ["900"]}
        ok, _, _ = await plugin.handle_command(text="/hd diag", stream_id="s", group_id="100")
        assert ok is False and "管理指令" in replies[-1]
        assert rendered == [] and sent == []

    asyncio.run(scenario())


@pytest.mark.parametrize("config,group_id,operator", [
    ({}, "100", False),
    ({"allowed_groups": []}, "100", False),
    ({"allowed_groups": ["200"], "admin_users": ["900"]}, "100", False),
    ({"allowed_groups": ["200"]}, "100", True),
    ({"allowed_groups": ["100"], "admin_users": ["900"]}, "", True),
])
@pytest.mark.parametrize("action", ["loadout", "status", "help", "diag"])
def test_all_commands_require_a_configured_group_even_for_admins(
    config: dict, group_id: str, operator: bool, action: str
) -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, rendered, sent = loadout_plugin(replies)
        plugin._cfg = config
        ok, why, _ = await plugin.handle_command(
            text=f"/hd {action}", stream_id="s", group_id=group_id,
            user_id="900", is_local_operator=operator,
        )
        assert ok is False and "白名单" in why
        assert "白名单" in replies[-1]
        assert rendered == [] and sent == [] and plugin._loadout_sessions == {}

    asyncio.run(scenario())


def test_group_allowlist_reload_grants_and_revokes_commands_immediately() -> None:
    async def scenario() -> None:
        replies: list[str] = []
        plugin, rendered, sent = loadout_plugin(replies)
        plugin._cfg = {"allowed_groups": []}
        command = {"text": "/hd loadout", "stream_id": "s", "group_id": "100", "user_id": "u1"}
        assert (await plugin.handle_command(**command))[0] is False
        await plugin.on_config_update(config_data={"plugin": {"allowed_groups": ["100"]}})
        assert (await plugin.handle_command(**command))[0] is True
        assert len(rendered) == len(sent) == 1
        await plugin.on_config_update(config_data={"plugin": {"allowed_groups": []}})
        command["text"] = "/hd loadout 3"
        assert (await plugin.handle_command(**command))[0] is False
        assert len(rendered) == len(sent) == 1

    asyncio.run(scenario())


def test_group_allowlist_accepts_unquoted_group_numbers() -> None:
    config = PluginConfig.model_validate({"plugin": {"allowed_groups": [100]}})
    assert config.model_dump()["plugin"].get("allowed_groups") == ["100"]

    async def scenario() -> None:
        plugin = command_plugin([])
        plugin._cfg = {"allowed_groups": [100]}
        assert (await plugin.handle_command(text="/hd status", group_id=100, stream_id="s"))[0] is True

    asyncio.run(scenario())


# ── MaiBot 1.4 compatibility ────────────────────────────────────────────────
# 1.4 换了次版本号的兼容区间、给每个实例独立的 data_dir，并把当前插件配置随
# 命令一起传进处理器。下面这些用例把三处变化钉在宿主行为上，而不是钉在实现上。


def test_manifest_accepts_maiBot_1_4_hosts() -> None:
    """1.4 是新的次版本，旧的 1.3.99 上限会让 ManifestValidator 直接拒绝加载。"""
    manifest = load_manifest()
    host = manifest["host_application"]
    assert host["max_version"] == "1.4.99"
    assert tuple(map(int, host["min_version"].split("."))) < (1, 4, 0), "老宿主仍要能装"
    assert tuple(map(int, manifest["sdk"]["max_version"].split("."))) >= (2, 22, 0), (
        "MaiBot 1.4 随附 SDK 2.22.1，区间必须覆盖它"
    )


def test_command_declares_a_public_permission_for_the_1_4_catalog() -> None:
    """1.4 在进入处理器之前就会拦截 permission=operator 的命令。

    本插件把公开动作和管理指令 diag 放在同一个组件里，所以只能声明 public 再按
    动作自行判定；宿主侧的插件权限与命令权限列表依然叠加生效。
    """
    info = getattr(DemocracyChoosesPlugin.handle_command, "__maibot_component_info__", None)
    meta = dict(getattr(info, "metadata", info) or {})
    assert meta.get("permission") == "public"
    assert ADMIN_ACTIONS == {"diag"}, "管理动作若变多，需要重新审视上面的 public 声明"


def test_equipment_data_is_seeded_into_the_instance_data_directory(tmp_path: Path) -> None:
    """1.4 每个实例只有自己的 data_dir；升级覆盖源码目录不能删掉玩家改动。"""

    async def scenario() -> None:
        plugin = DemocracyChoosesPlugin()

        class Ctx:
            class paths:
                data_dir = tmp_path / "instance"

        attach_ctx(plugin, Ctx())
        seeded = plugin._data_file("loadout_data.json")
        assert seeded == tmp_path / "instance" / "loadout_data.json"
        assert seeded.read_text(encoding="utf-8") == (BUNDLE_DIR / "loadout_data.json").read_text(encoding="utf-8")
        # 图标有十几 MB 且不需要玩家编辑：就地读取，不复制。
        assert plugin._data_file("loadout_icons.json") == BUNDLE_DIR / "loadout_icons.json"
        # 真正被读取的是副本，所以改副本立即生效。
        seeded.write_text('{"items": [{"slot": "primary", "name": "测试步枪"}]}', encoding="utf-8")
        assert load_loadout_pool(plugin._data_file("loadout_data.json"))["primary"] == ["测试步枪"]

    asyncio.run(scenario())


def test_tag_knowledge_is_seeded_per_instance_and_prefers_excel(tmp_path: Path) -> None:
    """标签表也属于可编辑数据：播种到实例目录，Excel 优先、删掉后回落到 CSV。"""

    async def scenario() -> None:
        plugin = DemocracyChoosesPlugin()

        class Ctx:
            class paths:
                data_dir = tmp_path / "instance"

        attach_ctx(plugin, Ctx())
        table = plugin._knowledge_table()
        assert table == tmp_path / "instance" / "loadout_tags.xlsx"
        assert table.exists(), "首次使用应从插件目录播种"
        assert plugin._data_file("loadout_knowledge.json").exists()
        # 维护者删掉工作簿改用 CSV 时，不能被悄悄重新播种。
        table.unlink()
        csv_copy = tmp_path / "instance" / "loadout_tags.csv"
        csv_copy.write_text("id\n", encoding="utf-8")
        assert plugin._knowledge_table() == csv_copy

    asyncio.run(scenario())


def test_two_instances_never_share_an_equipment_list(tmp_path: Path) -> None:
    """多实例是 1.4 的主打功能：两个实例各一份装备清单，互不覆盖。"""

    async def scenario() -> None:
        def instance(name: str) -> DemocracyChoosesPlugin:
            plugin = DemocracyChoosesPlugin()

            class Ctx:
                class paths:
                    data_dir = tmp_path / name

            attach_ctx(plugin, Ctx())
            return plugin

        first, second = instance("bot-a"), instance("bot-b")
        first._data_file("loadout_data.json").write_text(
            '{"items": [{"slot": "primary", "name": "甲"}]}', encoding="utf-8"
        )
        assert load_loadout_pool(first._data_file("loadout_data.json"))["primary"] == ["甲"]
        # 第二个实例拿到的仍是自己的初始副本，没有被第一个实例的改动污染。
        assert load_loadout_pool(second._data_file("loadout_data.json"))["primary"] != ["甲"]

    asyncio.run(scenario())


def test_hosts_without_data_paths_keep_reading_the_bundled_files() -> None:
    """1.3 及更老的宿主没有 ctx.paths：行为必须与升级前完全一致。"""

    async def scenario() -> None:
        plugin = DemocracyChoosesPlugin()
        attach_ctx(plugin, object())
        assert plugin._data_dir() == BUNDLE_DIR
        assert plugin._data_file("loadout_data.json") == BUNDLE_DIR / "loadout_data.json"

    asyncio.run(scenario())


def test_unusable_data_directory_falls_back_to_the_bundled_file(tmp_path: Path) -> None:
    """数据目录建不出来时，不能连配装都抽不出来。"""

    async def scenario() -> None:
        plugin = DemocracyChoosesPlugin()
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("", encoding="utf-8")  # 同名文件，mkdir 必然失败

        class Ctx:
            class paths:
                data_dir = blocker / "instance"

        attach_ctx(plugin, Ctx())
        assert plugin._data_file("loadout_data.json") == BUNDLE_DIR / "loadout_data.json"
        assert load_loadout_pool(plugin._data_file("loadout_data.json"))

    asyncio.run(scenario())


def test_command_adopts_the_live_config_maiBot_1_4_injects() -> None:
    """1.4 把当前插件配置随命令传进来；漏掉一次广播也不能继续用旧白名单。"""

    async def scenario() -> None:
        replies: list[str] = []
        plugin, rendered, sent = loadout_plugin(replies)
        plugin._cfg = {}  # 还没从 runner 拿到任何配置
        ok, _, _ = await plugin.handle_command(
            text="/hd loadout",
            stream_id="s",
            user_id="u1",
            group_id="100",
            plugin_config={"plugin": {"allowed_groups": ["100"], "loadout_reroll_seconds": 90}},
        )
        assert ok and len(rendered) == len(sent) == 1
        assert plugin._cfg["allowed_groups"] == ["100"]
        assert plugin._loadout_reroll_seconds() == 90

    asyncio.run(scenario())


def test_empty_plugin_config_never_wipes_loaded_settings() -> None:
    """宿主读不到配置时会传空表；那不等于"把白名单清空"。"""

    async def scenario() -> None:
        replies: list[str] = []
        plugin, _, _ = loadout_plugin(replies)
        plugin._cfg = {"allowed_groups": ["100"]}
        ok, _, _ = await plugin.handle_command(
            text="/hd status", stream_id="s", user_id="u1", group_id="100", plugin_config={}
        )
        assert ok
        assert plugin._cfg == {"allowed_groups": ["100"]}

    asyncio.run(scenario())


def test_status_reports_the_data_directory_and_reads_it(tmp_path: Path) -> None:
    """多实例排查的第一件事：这个实例到底读的哪份数据。"""

    async def scenario() -> None:
        replies: list[str] = []
        plugin = command_plugin(replies)

        class Ctx:
            class paths:
                data_dir = tmp_path / "instance"

        attach_ctx(plugin, Ctx())
        ok, _, _ = await plugin.handle_command(
            text="/hd status", stream_id="s", user_id="u1", group_id="100"
        )
        assert ok
        assert str(tmp_path / "instance") in replies[-1]
        assert "配装标签" in replies[-1], "标签库应从实例目录读取并通过校验"

    asyncio.run(scenario())
