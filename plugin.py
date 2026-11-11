"""Offline Helldivers 2 loadout generator for MaiBot."""
from __future__ import annotations

import html
import json
import logging
import random
import re
import shutil
import time
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__:
    from .experimental_groups import ExperimentalGroups, ExperimentalGroupsError
    from .loadout_experiment import (
        ExperimentError, TemplateCatalog, generate_experimental_loadout, load_templates, reroll_experimental_slot,
    )
    from .loadout_knowledge import KnowledgeError, load_knowledge
else:
    from experimental_groups import ExperimentalGroups, ExperimentalGroupsError
    from loadout_experiment import (
        ExperimentError, TemplateCatalog, generate_experimental_loadout, load_templates, reroll_experimental_slot,
    )
    from loadout_knowledge import KnowledgeError, load_knowledge


try:  # maibot-plugin-sdk 2.x
    from maibot_sdk import (  # type: ignore
        CONFIG_RELOAD_SCOPE_SELF,
        Command,
        Field,
        MaiBotPlugin,
        PluginConfigBase,
    )
    from pydantic import ConfigDict  # type: ignore
except ImportError as sdk_import_error:  # importing should still support isolated tests
    logging.getLogger(__name__).warning(
        "maibot-plugin-sdk is unavailable; DemocracyChooses is using test-only SDK stubs: %s",
        sdk_import_error,
    )
    CONFIG_RELOAD_SCOPE_SELF = "self"

    class PluginConfigBase:
        pass

    def ConfigDict(**kwargs: Any) -> Any:
        return dict(kwargs)

    def Field(default: Any = None, default_factory: Any = None, **_: Any) -> Any:
        return default_factory() if default_factory else default

    class MaiBotPlugin:
        ctx: Any

    def Command(
        name: str = "",
        description: str = "",
        pattern: str = "",
        aliases: Any = None,
        **metadata: Any,
    ):
        """Stand-in mirroring the SDK decorator so tests can inspect the metadata.

        Mirrors the real signature (``name`` / ``description`` / ``pattern`` /
        ``aliases`` plus free-form metadata) so a test assertion behaves the same
        with or without the SDK installed.
        """

        def decorate(fn: Any) -> Any:
            setattr(
                fn,
                "__maibot_component_info__",
                {
                    "name": name,
                    "description": description,
                    "command_pattern": pattern,
                    "aliases": list(aliases or []),
                    **metadata,
                },
            )
            return fn

        return decorate


# ── random loadout generator ────────────────────────────────────────────────
# Item names live in a data file next to this module so the game data can be
# refreshed without touching the code. Icons are baked into a second file as
# data URIs because ``render.html2png`` defaults to ``allow_network=False``, so
# the card HTML must not reference anything outside itself.
LOADOUT_DATA_FILE = Path(__file__).with_name("loadout_data.json")
LOADOUT_ICONS_FILE = Path(__file__).with_name("loadout_icons.json")
# MaiBot 1.4 can host several bots inside one MAIBOT, and every instance owns a
# separate ``data/plugins/<plugin id>`` directory (``ctx.paths.data_dir`` in the
# SDK). User editable game data and the tag knowledge base belong there:
# replacing this source tree on a plugin update can no longer wipe the edits, and
# two instances never share one equipment list or one tag table. ``BUNDLE_DIR``
# stays the fallback for hosts without the path API (MaiBot 1.3 and older) and
# for tests.
BUNDLE_DIR = Path(__file__).resolve().parent
# Seeded into the data directory on first use. Only files users are expected to
# edit are copied; the multi-megabyte icon bundle is read in place unless a copy
# already exists in the data directory.
EDITABLE_DATA_FILES = frozenset({"loadout_data.json", "loadout_knowledge.json", "loadout_tags.xlsx"})
KNOWLEDGE_TABLES = ("loadout_tags.xlsx", "loadout_tags.csv")
LOADOUT_SLOTS = ("primary", "secondary", "grenade", "booster")
LOADOUT_SLOT_LABELS = {
    "primary": "主武器",
    "secondary": "副武器",
    "grenade": "投掷物",
    "booster": "强化资源",
    "stratagem": "战略配备",
}
LOADOUT_STRATAGEM_COUNT = 4
LOADOUT_CARD_WIDTH = 1080
# Taller than the icon-less mock-up: every slot now reserves room for its art.
LOADOUT_CARD_HEIGHT = 1880
LOADOUT_MOTTOS = (
    "装备全随机，超级地球认可你的勇气。",
    "这套配置由超级地球武装部随机配发。",
    "相信指挥部的判断，潜兵。",
    "随机也是一种信仰，民主不需要最优解。",
    "解放你大业的！装备齐了，准备投放！",
    "你负责扣扳机，民主负责解释战果。",
    "装备已经批准，生还申请请另行提交。",
    "你的意见很重要，军需部已替你填写。",
    "本次配发手续齐全，战术价值由你现场补充。",
    "对配装有疑问？请向最近的民主官咨询。",
    "请放心投放，下一位增援已在冷冻舱候命。",
    "样本优先回收，潜兵按需补充。",
    "友军伤害无需申请，责任认定另走流程。",
    "军需部已完成抽签，解释权归超级地球所有。",
    "投放坐标尚未确认，抚恤申请已提前建档。",
    "重抽申请已经受理，独立思考暂缓执行。",
    "你每多想一秒，敌人就多活一秒。",
    "别问能不能打，问就是已通过军需验收。",
    "你可以质疑配装，民主官可以质疑你。",
    "超级地球感谢你的服役，下一份感谢信已在打印。",
)
LOADOUT_FOOTER = "绝地潜兵 2：民主帮你选择 · 随机配装"
# Lazily filled by ``load_loadout_icons``; ``None`` means "not read yet".
# ``_LOADOUT_ICONS_CACHE_PATH`` is the file the cache holds, so a second
# instance reading a different icon file does not get the first one's data.
_LOADOUT_ICONS_CACHE: dict[str, str] | None = None
_LOADOUT_ICONS_CACHE_PATH: Path | None = None
# ``/helldivers loadout <1-8>`` re-draws a single card of the loadout that was
# generated within this many seconds. The window slides on every reroll so a
# series of rerolls cannot be cut off halfway.
LOADOUT_REROLL_TTL_SECONDS = 120
# Card order as drawn on the image (two 2x2 grids, read left to right, top to
# bottom), which is the numbering the user sees and counts.
LOADOUT_SLOT_CHOICES: dict[int, str] = {
    1: "primary",
    2: "secondary",
    3: "grenade",
    4: "booster",
    5: "stratagem_0",
    6: "stratagem_1",
    7: "stratagem_2",
    8: "stratagem_3",
}
LOADOUT_INDEX_WORDS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
LOADOUT_SLOT_HINT = "1 主武器 / 2 副武器 / 3 投掷物 / 4 强化资源 / 5-8 战略配备"
# Tiny self-contained page for ``/helldivers diag``: it exercises the exact same
# render call the real card uses, so a failure here explains a text-only fallback.
DIAG_HTML = (
    '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><style>'
    f"body {{ width:{LOADOUT_CARD_WIDTH}px; min-height:{LOADOUT_CARD_HEIGHT}px; margin:0;"
    "display:flex; flex-direction:column; align-items:center; justify-content:center; gap:26px;"
    "background:linear-gradient(180deg,#101720,#05080c); color:#f5cb3d;"
    'font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif; }'
    ".big { font-size:78px; font-weight:900; letter-spacing:4px; }"
    ".small { color:#a7afb8; font-size:31px; }"
    '</style></head><body><div class="big">渲染自检 OK</div>'
    '<div class="small">这条消息是图片，说明渲染链路正常</div></body></html>'
)
# A cold browser start -- and a possible Chromium download -- can outlive the
# host's ordinary component budget. Both relevant budgets are raised explicitly:
# ``call_capability(timeout_ms=...)`` sets the RPC timeout separately from the
# capability arguments, and ``@Command(..., timeout_ms=...)`` raises the command's
# own RPC budget above it.
RENDER_RPC_TIMEOUT_MS = 150_000
COMMAND_RPC_TIMEOUT_MS = 180_000


# The subcommand is a *named* group so the host exposes it as
# ``matched_groups["action"]``; the same pattern is reused to re-parse the raw
# text when a host only provides unnamed groups.
# Trigger words. The host resolves a command by ``pattern.search(text)`` first and
# falls back to ``text.startswith(alias)`` (empty named groups), so both the regex
# and the registered aliases have to be generated from one list -- otherwise a
# short form would reach the handler without ever matching the pattern.
COMMAND_NAME = "helldivers"
COMMAND_TRIGGERS = (COMMAND_NAME, "hd", "潜兵", "绝地潜兵")
# Slash-prefixed: the host prefix-matches every incoming message against these, so
# a bare word like ``hd`` would swallow ordinary chat.
COMMAND_ALIASES = tuple(f"/{name}" for name in COMMAND_TRIGGERS if name != COMMAND_NAME)
TRIGGER_ALTERNATION = "|".join(re.escape(name) for name in COMMAND_TRIGGERS)
COMMAND_PATTERN = (
    rf"^/(?:{TRIGGER_ALTERNATION})"
    r"(?:\s+(?:(?P<exp>(?i:exp))(?:\s+(?P<exp_arg>\w+(?:\s+[\w-]+)?))?"
    r"|(?P<action>\w+)(?:\s+(?P<arg>\w+))?))?\s*$"
)
COMMAND_RE = re.compile(COMMAND_PATTERN, re.IGNORECASE)


ACTION_LABELS = {'loadout': '配装', 'status': '状态', 'diag': '自检', 'help': '帮助', 'exp': '实验配装'}


LETTER_SHORTCUTS = (('lo', 'loadout'), ('st', 'status'), ('diag', 'diag'), ('h', 'help'))


SINGLE_CHAR_SHORTCUTS = (('装', 'loadout'), ('态', 'status'), ('诊', 'diag'), ('助', 'help'))


ACTION_ALIASES = {
    "状态": "status", "帮助": "help", "配装": "loadout", "随机配装": "loadout", "配装生成": "loadout",
    "诊断": "diag", "自检": "diag", "检测": "diag", "测试": "diag",
    **dict(LETTER_SHORTCUTS), **dict(SINGLE_CHAR_SHORTCUTS),
}
COMMAND_ACTIONS = frozenset({"loadout", "status", "diag", "help", "exp"})
FUNCTIONAL_ACTIONS = frozenset({"loadout", "status", "help", "exp"})
ADMIN_ACTIONS = frozenset({"diag"})
EXPERIMENT_MANAGEMENT = frozenset({"on", "off", "status"})
EXPERIMENT_FACTIONS = {
    "any": "any", "通用": "any",
    "terminids": "terminids", "东线": "terminids",
    "automatons": "automatons", "西线": "automatons",
    "illuminate": "illuminate", "南线": "illuminate",
}


@dataclass(frozen=True)
class ExperimentalSession:
    template_id: str
    template_name: str
    loadout: dict[str, str]
    updated_at: float


def pad_display(text: str, width: int) -> str:
    """Left-align ``text`` in ``width`` terminal columns.

    ``str.ljust`` counts characters, but CJK glyphs occupy two columns, so
    ``格式化`` tables built with ``:<10`` end up ragged.
    """
    columns = sum(2 if unicodedata.east_asian_width(ch) in {"W", "F"} else 1 for ch in text)
    return text + " " * max(0, width - columns)


def topic_loadout(plugin: Any) -> str:
    reroll = plugin._loadout_reroll_seconds()
    return (
        "【/helldivers loadout】随机生成一套配装并发图\n"
        "从主武器、副武器、投掷物、强化资源各随机一件，再随机四件互不重复的战略配备，\n"
        "渲染成一张配装卡片图发送；宿主不支持出图时自动回退为文字。\n"
        f"卡片左上角的编号就是槽位号，抽完之后 {reroll} 秒内可以只重抽其中一格：\n"
        f"  /helldivers loadout 3   只重抽第 3 格（也可以在 {reroll} 秒内一直重抽下去）\n"
        f"槽位号：{LOADOUT_SLOT_HINT}\n"
        f"每重抽一次倒计时重新开始；时间窗可在 config.toml 的 plugin.loadout_reroll_seconds 调整。\n"
        "超过时间或还没抽过时，重抽会提示你先抽一套。\n"
        "中文写法：/helldivers 配装 或 /helldivers 随机配装\n"
        "装备清单读取插件数据目录里的 loadout_data.json"
        "（MaiBot 1.4 为 data/plugins/<插件 ID>/，首次使用时从插件目录复制），可自行增删。"
    )


def usage_hint(*, reroll: int = LOADOUT_REROLL_TTL_SECONDS) -> str:
    """Usage rendered from the live reroll window."""
    return (
        "绝地潜兵 2：民主帮你选择\n用法：\n"
        "/helldivers loadout     生成一套随机配装并以图片发送\n"
        f"                        抽完 {reroll} 秒内可加序号 1-8 单独重抽该格\n"
        "/helldivers exp         实验配装与本群实验白名单\n"
        "/helldivers status      查看配装数据与出图状态\n"
        "/helldivers diag        自检出图链路（管理指令）\n"
        "/helldivers help [主题] 查看帮助，带主题看单条命令详情\n"
        "管理指令只有 admin_users 白名单管理员与宿主操作员能用；"
        "白名单群内其余指令默认所有人可用，可单独加黑名单。\n"
        "所有指令仅限 allowed_groups 白名单群，私聊不可用；管理员与宿主操作员同样受限。\n"
        "基础群白名单在 plugin.allowed_groups 中维护，实验白名单由群内管理指令维护。\n"
        "动作简写："
        + " / ".join(f"{shortcut} {ACTION_LABELS[action]}" for shortcut, action in LETTER_SHORTCUTS)
        + "\n单字简写：" + " / ".join(shortcut for shortcut, _ in SINGLE_CHAR_SHORTCUTS)
        + "\n可用主题：loadout / exp / status / diag / help / shortcut\n"
        "中文写法：/helldivers 配装、/helldivers 帮助 配装\n"
        f"触发词：{' / '.join('/' + name for name in COMMAND_TRIGGERS)}（完全等价）"
    )


def topic_shortcut(plugin: Any) -> str:
    del plugin
    rows = [
        f"  {pad_display(shortcut, 8)}{pad_display(ACTION_LABELS[action], 12)}/hd {shortcut}"
        for shortcut, action in LETTER_SHORTCUTS
    ]
    return "\n".join([
        "【/helldivers 简写】触发词与简写",
        f"触发词：{' / '.join('/' + name for name in COMMAND_TRIGGERS)} 完全等价",
        "字母简写：", *rows,
        "单字中文：" + " / ".join(f"{shortcut}={ACTION_LABELS[action]}" for shortcut, action in SINGLE_CHAR_SHORTCUTS),
        "中文写法：/helldivers 简写（也可写 shortcut / 快捷 / 缩写）",
    ])


HELP_TOPICS = {
    "loadout": topic_loadout,
    "exp": (
        "【/helldivers exp】实验配装\n"
        "管理员可用 /hd exp on、/hd exp off 或 /hd exp status 管理当前群。\n"
        "/hd exp loadout 抽通用推进模板。可加阵营或模板 ID。\n"
        "/hd exp presets [阵营] 查看模板 ID，/hd exp loadout 1-8 重抽一格。\n"
        "中文写法：/潜兵 exp loadout 东线（也可选西线、南线或通用）"
    ),
    "diag": (
        "【/helldivers diag】自检出图链路（管理指令）\n"
        "检查配装数据与装备图标，再渲染并发送测试图。失败会显示宿主返回的原因，"
        "请检查 MaiBot 配置 plugin_runtime.render.enabled，以及 Playwright 与 Chromium。\n"
        "只有 admin_users 白名单管理员与宿主操作员可以使用。\n"
        "中文写法：/helldivers 诊断 / 自检 / 测试"
    ),
    "status": (
        "【/helldivers status】查看配装状态\n"
        "显示装备数据、图标数量、重抽时间窗、当前实例的数据目录与最近一次出图异常。\n"
        "中文写法：/helldivers 状态"
    ),
    "help": (
        "【/helldivers help [主题]】显示用法\n"
        "不带主题显示全部命令；带主题看单条命令详情，例如 /helldivers help loadout。\n"
        "可用的主题：loadout / exp / status / diag / help / shortcut\n"
        "中文写法：/helldivers 帮助，或 /helldivers 帮助 配装\n"
        "简写清单见 /helldivers help 简写（也可写 shortcut / 快捷 / 缩写）"
    ),
    "shortcut": topic_shortcut,
}
HELP_ONLY_ALIASES = {"简写": "shortcut", "快捷": "shortcut", "缩写": "shortcut", "快捷方式": "shortcut", "简称": "shortcut"}


class PluginSection(PluginConfigBase):
    """Allowed groups, permissions and the loadout reroll window."""
    model_config = ConfigDict(validate_assignment=True, extra="ignore", coerce_numbers_to_str=True)
    __ui_label__ = "绝地潜兵 2：民主帮你选择"
    __ui_icon__ = "gamepad-2"
    __ui_order__ = 10

    allowed_groups: list[str] = Field(
        default_factory=list,
        description=(
            "允许使用本插件所有指令的群号白名单，只能在配置文件中添加。"
            "默认空列表表示所有群均不可用；私聊不可用，管理员与宿主操作员也不能绕过。"
        ),
        json_schema_extra={
            "label": "允许使用的群（白名单）", "group": "权限", "order": 1,
            "hint": "仅通过 config.toml 的 plugin.allowed_groups 维护", "example": ["123456789"],
            "hidden": True,
        },
    )

    admin_users: list[str] = Field(
        default_factory=list,
        description=(
            "出图自检和实验白名单管理指令的管理员 QQ 号。功能性指令（配装/状态/帮助）"
            "在允许群内默认所有人都能用，不需要写在这里。宿主操作员在允许群内拥有管理权限。"
        ),
        json_schema_extra={
            "label": "管理员 QQ 号（白名单）",
            "group": "权限",
            "order": 5,
            "hint": "每行一个 QQ 号；只有这里的人能用管理指令",
            "example": ["123456789"],
        },
    )

    command_blacklist: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "功能性指令的黑名单：键是指令名（loadout / "
            "exp / status / help，或 * 表示全部功能性指令），值是禁止使用该指令的 QQ 号列表。"
            "管理指令不受此表影响（它们本来就是白名单制）；管理员也不会被此表拦住。"
        ),
        json_schema_extra={
            "label": "指令黑名单",
            "group": "权限",
            "order": 6,
            "hint": '例如 {"*": ["10001"], "loadout": ["10002"]}',
            "example": {"loadout": ["10001"]},
        },
    )

    loadout_reroll_seconds: int = Field(
        default=LOADOUT_REROLL_TTL_SECONDS,
        ge=10,
        le=3600,
        description=(
            "抽完配装后还能用 /helldivers loadout <1-8> 单独重抽的时间窗（秒）。"
            "每重抽一次倒计时重新开始，可以连着抽到满意为止；超时后需要重新抽一整套。"
        ),
        json_schema_extra={"label": "配装重抽时间窗（秒）", "group": "随机配装", "order": 30, "example": 300},
    )


class PluginConfig(PluginConfigBase):
    plugin: PluginSection = Field(default_factory=PluginSection)


def _parse_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    value = raw.get("plugin", raw)
    return dict(value) if isinstance(value, Mapping) else {}


def _load_local_config() -> dict[str, Any]:
    """Load a colocated config.toml when MaiBot has not injected settings."""
    path = Path(__file__).with_name("config.toml")
    if not path.exists():
        return {}
    try:
        import tomllib
        with path.open("rb") as handle:
            return _parse_config(tomllib.load(handle))
    except Exception:
        return {}


class DemocracyChoosesPlugin(MaiBotPlugin):
    config_model = PluginConfig

    def __init__(self, *args: Any, **kwargs: Any):
        try:
            super().__init__(*args, **kwargs)
        except TypeError:
            super().__init__()
        self._cfg: dict[str, Any] = {}
        # scope -> (loadout, motto, monotonic stamp); powers ``loadout <1-8>``.
        self._loadout_sessions: dict[str, tuple[dict[str, str], str, float]] = {}
        self._experimental_sessions: dict[tuple[str, str], ExperimentalSession] = {}
        # Why the last card render / image send failed; empty after a success.
        self._last_render_error = ""
        # Resolved lazily: ``ctx.paths`` only exists inside a runner, and the
        # directory is per instance (MaiBot 1.4 multi-instance).
        self._data_dir_path: Path | None = None

    async def on_load(self) -> None:
        raw: Any = {}
        try:
            raw = self.get_plugin_config_data()  # type: ignore[attr-defined]
        except Exception:
            pass
        self._cfg = _parse_config(raw) or _load_local_config()

    async def on_unload(self) -> None:
        self._loadout_sessions.clear()
        self._experimental_sessions.clear()

    async def on_config_update(self, scope: str = CONFIG_RELOAD_SCOPE_SELF, config_data: Any = None, version: str = "") -> None:
        del version
        if isinstance(scope, Mapping):
            config_data, scope = scope, CONFIG_RELOAD_SCOPE_SELF
        if scope not in (CONFIG_RELOAD_SCOPE_SELF, "self", ""):
            return
        self._cfg = _parse_config(config_data) or _load_local_config()

    def _cfg_int(self, key: str, default: int, minimum: int = 0) -> int:
        """Read an int tunable, tolerating a hand-edited config.toml.

        ``self._cfg`` is the raw dict, not a validated model instance, so a typo in
        the file must not break a command.
        """
        try:
            return max(minimum, int(self._cfg.get(key, default)))
        except (TypeError, ValueError):
            self._log("warning", "Helldivers config %s is not a number, falling back to %s", key, default)
            return default

    def _actor_id(self, kwargs: Mapping[str, Any]) -> str:
        return str(kwargs.get("user_id") or "").strip()

    def _data_dir(self) -> Path:
        """Per-instance data directory, resolved once per plugin instance."""
        if self._data_dir_path is None:
            try:
                context: Any = self.ctx
            except (AttributeError, RuntimeError):
                context = None
            self._data_dir_path = resolve_data_dir(context)
        return self._data_dir_path

    def _data_file(self, name: str) -> Path:
        """Active path of one data file; seeds the data directory on first use."""
        return data_file(name, self._data_dir())

    def _knowledge_table(self) -> Path:
        """Tag table of this instance: Excel first, then CSV, else the seeded copy.

        A maintainer who removed the workbook to work from CSV keeps that choice:
        resolving the table must not re-seed a file they deleted on purpose.
        """
        base = self._data_dir()
        for name in KNOWLEDGE_TABLES:
            candidate = base / name
            if candidate.exists():
                return candidate
        return data_file(KNOWLEDGE_TABLES[0], base)

    def _apply_command_config(self, kwargs: Mapping[str, Any]) -> None:
        """Adopt the live config MaiBot 1.4 attaches to every command call.

        The runner already pushes ``on_config_update`` when the file changes, but
        1.4 additionally hands the handler the current ``plugin_config``; reading
        it keeps the group white list correct when a broadcast was missed. An
        empty payload must never wipe a working configuration.
        """
        injected = kwargs.get("plugin_config")
        if not isinstance(injected, Mapping) or not injected:
            return
        parsed = _parse_config(injected)
        if parsed and parsed != self._cfg:
            self._cfg = parsed

    def _cfg_id_list(self, key: str) -> set[str]:
        """Read a list of QQ numbers, tolerating a bare string or a TOML table."""
        value = self._cfg.get(key)
        if isinstance(value, str):
            rows: Iterable[Any] = [value]
        elif isinstance(value, Mapping):
            rows = list(value)  # a TOML inline table used as a plain set
        elif isinstance(value, (list, tuple, set)):
            rows = value
        else:
            return set()
        return {str(item).strip() for item in rows if str(item).strip()}

    def _command_blacklist(self) -> dict[str, set[str]]:
        """``{action or '*': {user_id, ...}}`` from the ``command_blacklist`` table."""
        value = self._cfg.get("command_blacklist")
        if not isinstance(value, Mapping):
            return {}
        result: dict[str, set[str]] = {}
        for raw_action, raw_users in value.items():
            if isinstance(raw_users, str):
                users: Iterable[Any] = [raw_users]
            elif isinstance(raw_users, (list, tuple, set)):
                users = raw_users
            else:
                continue
            blocked = {str(user).strip() for user in users if str(user).strip()}
            if not blocked:
                continue
            key = str(raw_action).strip()
            key = "*" if key in {"*", "all", "全部", "所有"} else ACTION_ALIASES.get(key, key)
            result.setdefault(key, set()).update(blocked)
        return result

    def _is_admin(self, kwargs: Mapping[str, Any]) -> bool:
        """Host operator, or a user named in the ``admin_users`` whitelist."""
        if kwargs.get("is_local_operator") is True:
            return True
        actor = self._actor_id(kwargs)
        return bool(actor) and actor in self._cfg_id_list("admin_users")

    def _command_permission(self, kwargs: Mapping[str, Any], action: str) -> str:
        """Reason this user may not run this action, or an empty string when allowed.

        Functional commands are open to everyone unless blacklisted; management
        commands are whitelist-only. The host operator and anyone in
        ``admin_users`` pass both, so a blacklist can never lock an admin out.
        """
        if not action or self._is_admin(kwargs):
            return ""
        if action in ADMIN_ACTIONS:
            return "这是管理指令，只有管理员可以使用"
        actor = self._actor_id(kwargs)
        if not actor:
            return ""
        blocked = self._command_blacklist()
        if actor in blocked.get("*", set()) or actor in blocked.get(action, set()):
            return "你已被禁止使用该指令"
        return ""

    def _loadout_reroll_seconds(self) -> int:
        return self._cfg_int("loadout_reroll_seconds", LOADOUT_REROLL_TTL_SECONDS, 1)

    def _resolve_command(self, kwargs: Mapping[str, Any]) -> tuple[str, str]:
        """Return ``(action, argument)``, preferring the host's named matches.

        An empty ``action`` means the text reached us only because the host's alias
        check is a bare ``text.startswith(alias)`` -- e.g. ``/hdx`` -- so it is not
        a real command and must not fall through to a default action.
        """
        matched = kwargs.get("matched_groups")
        if not isinstance(matched, Mapping) or not (matched.get("action") or matched.get("exp")):
            result = COMMAND_RE.match(str(kwargs.get("text") or "").strip())
            if result is None:
                return "", ""
            matched = result.groupdict()
        if matched.get("exp"):
            return "exp", " ".join(str(matched.get("exp_arg") or "").lower().split())
        action = str(matched.get("action") or "").strip().lower()
        argument = str(matched.get("arg") or "").strip().lower()
        action = ACTION_ALIASES.get(action, action)
        if action in HELP_ONLY_ALIASES:
            # ``/hd 简写`` is shorthand for ``help shortcut``.
            return "help", HELP_ONLY_ALIASES[action]
        if not action:
            return "status", ""
        return action, argument

    def _usage_hint(self) -> str:
        """Usage list rendered from the live config, so it can never go stale."""
        return usage_hint(reroll=self._loadout_reroll_seconds())

    def _help_text(self, argument: str) -> str:
        """Full usage, or a single topic when an argument is given.

        Topics that mention a tunable are callables, so the help always shows the
        values the plugin is actually running with.
        """
        if not argument:
            return self._usage_hint()
        topic = HELP_ONLY_ALIASES.get(argument) or ACTION_ALIASES.get(argument, argument)
        detail = HELP_TOPICS.get(topic)
        if detail is None:
            return f"没有「{argument}」这个主题\n\n{self._usage_hint()}"
        return detail(self) if callable(detail) else detail

    async def _send_image(self, kwargs: Mapping[str, Any], image_base64: str) -> bool:
        """Send a rendered card to the originating chat stream."""
        stream_id = str(kwargs.get("stream_id") or "").strip()
        if not stream_id:
            self._last_render_error = "命令上下文里没有 stream_id，无法定位会话"
            return False
        if not image_base64:
            self._last_render_error = "没有可发送的图片数据"
            return False
        try:
            result = await self.ctx.send.image(image_base64, stream_id)
        except Exception as exc:
            self._last_render_error = f"发送图片异常：{exc}"
            self._log("warning", "Helldivers image send failed: %s", exc)
            return False
        if isinstance(result, Mapping):
            ok = bool(result.get("sent", result.get("success", False)))
            if not ok:
                self._last_render_error = f"发送图片被拒绝：{dict(result)}"
        else:
            ok = result is not False
            if not ok:
                self._last_render_error = "发送图片返回 False"
        if not ok:
            self._log("warning", "Helldivers image send rejected: %s", self._last_render_error)
        return ok

    async def _call_render(self, args: Mapping[str, Any]) -> Any:
        """Render through the SDK capability call so the RPC timeout can be raised.

        SDK 2.7.1+ exposes the public ``PluginContext.call_capability`` method,
        whose ``timeout_ms`` controls the RPC budget. The typed render proxy
        exposes the render parameters but not that transport budget, so a cold
        browser start can outlive its default. Current MaiBot also reads Command
        ``timeout_ms`` metadata via
        ``host/component_timeout.py``; the decorator deliberately forwards extra
        metadata. The typed fallback keeps exactly the same render arguments.
        """
        call_capability = getattr(self.ctx, "call_capability", None)
        if callable(call_capability):
            return await call_capability("render.html2png", timeout_ms=RENDER_RPC_TIMEOUT_MS, **args)
        # Older SDK builds only expose the typed proxy: no way to raise the budget.
        return await self.ctx.render.html2png(
            str(args["html"]),
            selector=str(args["selector"]),
            viewport=dict(args["viewport"]),
            device_scale_factor=float(args["device_scale_factor"]),
            full_page=bool(args["full_page"]),
            render_timeout_ms=int(args["render_timeout_ms"]),
            allow_network=bool(args["allow_network"]),
        )

    async def _render_card(self, card_html: str, *, label: str = "配装卡片") -> str:
        """Host-rendered PNG as base64; empty string when rendering is unavailable.

        The host answers a failed render with ``{"success": False, "error": ...}``
        instead of raising, so the reason has to be read out of the payload --
        otherwise the failure is invisible and the caller silently degrades.
        """
        try:
            result = await self._call_render(
                {
                    "html": card_html,
                    "selector": "body",
                    "viewport": {"width": LOADOUT_CARD_WIDTH, "height": LOADOUT_CARD_HEIGHT},
                    "device_scale_factor": 1.0,
                    "full_page": True,
                    "render_timeout_ms": RENDER_RPC_TIMEOUT_MS,
                    "allow_network": False,
                }
            )
        except Exception as exc:
            self._last_render_error = f"调用渲染能力异常：{exc}"
            self._log("warning", "Helldivers %s render raised: %s", label, exc)
            return ""
        if isinstance(result, Mapping):
            image = str(result.get("image_base64") or result.get("data") or "")
            if image:
                self._last_render_error = ""
                return image
            reason = str(result.get("error") or result.get("message") or "").strip()
            self._last_render_error = reason or "渲染服务没有返回图片数据"
            self._log(
                "warning",
                "Helldivers %s render returned no image (keys=%s): %s",
                label,
                sorted(result),
                self._last_render_error,
            )
            return ""
        text = str(result or "")
        if text:
            self._last_render_error = ""
            return text
        self._last_render_error = "渲染能力返回了空值"
        self._log("warning", "Helldivers %s render returned an empty value", label)
        return ""

    def _loadout_scope(self, kwargs: Mapping[str, Any]) -> str:
        """Per-user session key, so one member's reroll never touches another's."""
        stream = str(kwargs.get("stream_id") or "").strip()
        user = str(kwargs.get("user_id") or "").strip()
        return f"{stream}|{user}" if user else stream

    def _prune_loadout_sessions(self, now: float, ttl: int | None = None) -> None:
        window = self._loadout_reroll_seconds() if ttl is None else ttl
        expired = [key for key, item in self._loadout_sessions.items() if now - item[2] > window]
        for key in expired:
            del self._loadout_sessions[key]

    async def _diagnose(self, kwargs: Mapping[str, Any]) -> tuple[bool, str, int]:
        """Probe the image pipeline so a text-only loadout can be explained.

        A render failure used to be silent: the card quietly degraded to text and
        nothing said why. This command walks the same steps and reports the host's
        own error message.
        """
        pool = load_loadout_pool(self._data_file("loadout_data.json"))
        icons = load_loadout_icons(self._data_file("loadout_icons.json"))
        total = sum(len(names) for names in pool.values())
        missing = [name for names in pool.values() for name in names if name not in icons]
        lines = [
            "【绝地潜兵 2：民主帮你选择·自检】",
            f"配装数据：{total} 件（{'、'.join(f'{slot} {len(names)}' for slot, names in pool.items())}）"
            if pool
            else "配装数据：未加载（缺少 loadout_data.json）",
            f"装备图标：{len(icons)} 个" + (f"，缺 {len(missing)} 件" if missing else "，全覆盖"),
            f"重抽时间窗：{self._loadout_reroll_seconds()} 秒",
        ]
        started = time.monotonic()
        image = await self._render_card(DIAG_HTML, label="自检")
        elapsed = int((time.monotonic() - started) * 1000)
        if not image:
            lines.append(f"浏览器渲染：失败（{elapsed} ms）")
            reason = self._last_render_error or "未知"
            lines.append(f"失败原因：{reason}")
            if "E_TIMEOUT" in reason or "超时" in reason:
                lines.append(f"→ 渲染超时（本次上限 {RENDER_RPC_TIMEOUT_MS // 1000} 秒）。")
                lines.append("   首次渲染需要启动 Playwright 浏览器，必要时还会下载 Chromium，")
                lines.append("   比较慢；请等一两分钟后再发一次 /helldivers diag，就绪后通常几秒出图。")
            else:
                lines.append("→ 检查 MaiBot 配置 plugin_runtime.render.enabled 是否为 true；")
                lines.append("   以及宿主环境是否装了 playwright 和 Chromium。")
            await self._reply(kwargs, "\n".join(lines))
            return False, "渲染不可用", 2
        lines.append(f"浏览器渲染：成功（{elapsed} ms，PNG 约 {len(image) * 3 // 4 // 1024} KB）")
        sent = await self._send_image(kwargs, image)
        lines.append("图片发送：成功（上面那张就是测试图）" if sent else f"图片发送：失败（{self._last_render_error or '未知'}）")
        await self._reply(kwargs, "\n".join(lines))
        return sent, "自检通过" if sent else "图片发送失败", 2

    async def _send_loadout_card(
        self, kwargs: Mapping[str, Any], loadout: Mapping[str, str], motto: str, *, template_name: str = "",
    ) -> tuple[bool, str, int]:
        footer = f"绝地潜兵 2 实验配装 · {template_name}" if template_name else LOADOUT_FOOTER
        icons = load_loadout_icons(self._data_file("loadout_icons.json"))
        image = await self._render_card(render_loadout_html(loadout, motto=motto, footer=footer, icons=icons))
        if image and await self._send_image(kwargs, image):
            return True, "已发送配装图", 2
        reason = self._last_render_error or "未知原因"
        self._log("warning", "Helldivers loadout fell back to text: %s", reason)
        text = format_loadout(loadout, motto=motto, template_name=template_name)
        # Surface the reason: a silent text fallback is impossible to debug from chat.
        await self._reply(kwargs, f"{text}\n（配装图生成失败，已回退文字：{reason}）")
        return True, "已发送配装文本", 2

    async def _reroll_loadout(
        self,
        kwargs: Mapping[str, Any],
        pool: Mapping[str, Sequence[str]],
        scope: str,
        argument: str,
        now: float,
    ) -> tuple[bool, str, int]:
        """Re-draw one card of the loadout drawn within the last 120 seconds."""
        index = parse_loadout_index(argument)
        if index not in LOADOUT_SLOT_CHOICES:
            await self._reply(
                kwargs,
                f"序号需要在 1-8 之间（{LOADOUT_SLOT_HINT}）\n"
                f"用法：先发 /helldivers loadout 抽一套，再在 {self._loadout_reroll_seconds()} 秒内发 "
                "/helldivers loadout <序号> 重抽该格",
            )
            return False, "配装序号无效", 2
        session = self._loadout_sessions.get(scope)
        if session is None:
            await self._reply(
                kwargs,
                f"没有可重抽的配装，请先发 /helldivers loadout 抽一套\n"
                f"（重抽只在抽完之后 {self._loadout_reroll_seconds()} 秒内可用）",
            )
            return False, "没有可重抽的配装", 2
        loadout, motto, _ = session
        key = LOADOUT_SLOT_CHOICES[index]
        replacement = reroll_loadout_slot(pool, loadout, key)
        if replacement is None:
            await self._reply(kwargs, f"{loadout_slot_title(index)} 没有别的可选装备了")
            return False, "没有可选装备", 2
        loadout = {**loadout, key: replacement}
        # Sliding window: the countdown restarts so consecutive rerolls keep working.
        self._loadout_sessions[scope] = (loadout, motto, now)
        return await self._send_loadout_card(kwargs, loadout, motto)

    async def _random_loadout(self, kwargs: Mapping[str, Any], argument: str = "") -> tuple[bool, str, int]:
        """Roll a loadout, or re-draw one card of the previous roll."""
        pool = load_loadout_pool(self._data_file("loadout_data.json"))
        if not pool:
            await self._reply(kwargs, "没有找到配装数据（loadout_data.json），无法生成配装")
            return False, "缺少配装数据", 2
        scope = self._loadout_scope(kwargs)
        now = time.monotonic()
        self._prune_loadout_sessions(now)
        if argument:
            return await self._reroll_loadout(kwargs, pool, scope, argument, now)
        loadout = generate_loadout(pool)
        motto = random.choice(LOADOUT_MOTTOS)
        self._loadout_sessions[scope] = (loadout, motto, now)
        return await self._send_loadout_card(kwargs, loadout, motto)

    async def _experimental_command(
        self, kwargs: Mapping[str, Any], group_id: str, argument: str,
    ) -> tuple[bool, str, int]:
        subcommand, _, value = argument.partition(" ")
        if not subcommand:
            denial = self._command_permission(kwargs, "help")
            if denial:
                await self._reply(kwargs, denial)
                return False, denial, 2
            await self._reply(kwargs, self._help_text("exp"))
            return True, "已发送实验配装用法", 2
        managing = subcommand in EXPERIMENT_MANAGEMENT
        if managing and not self._is_admin(kwargs):
            message = "实验白名单只有插件管理员或宿主操作员可以管理"
        elif (managing and value) or (not managing and subcommand not in {"loadout", "presets"}):
            message = "实验指令格式无效，请用 /hd help exp 查看用法"
        elif not managing:
            message = self._command_permission(kwargs, "exp")
            if not message and subcommand == "loadout":
                message = self._command_permission(kwargs, "loadout")
        else:
            message = ""
        if message:
            await self._reply(kwargs, message)
            return False, message, 2

        data_dir = self._data_dir()
        state_dir = BUNDLE_DIR / "data" if data_dir == BUNDLE_DIR else data_dir
        groups = ExperimentalGroups(state_dir / "experimental_groups.json")
        try:
            if managing:
                if subcommand == "status":
                    enabled = groups.enabled(group_id)
                else:
                    enabled = subcommand == "on"
                    groups.set_enabled(group_id, enabled)
                    if not enabled:
                        self._experimental_sessions = {
                            key: session for key, session in self._experimental_sessions.items()
                            if key[0] != group_id
                        }
                status = "已启用" if enabled else "未启用"
                message = f"本群实验配装{status}。"
                if enabled:
                    message += " 可用 /hd exp loadout 抽取，或用 /hd exp presets 查看预设。"
                await self._reply(kwargs, message)
                return True, message, 2
            if not groups.enabled(group_id):
                message = "本群未启用实验配装，请联系管理员使用 /hd exp on"
                await self._reply(kwargs, message)
                return False, message, 2
        except ExperimentalGroupsError as exc:
            self._log("warning", "Experimental group allowlist is unavailable: %s", exc)
            message = "实验白名单读写失败，请管理员检查数据目录中的 experimental_groups.json"
            await self._reply(kwargs, message)
            return False, message, 2

        choice = EXPERIMENT_FACTIONS.get(value, value or "any")
        try:
            catalog = load_templates(self._data_file("loadout_templates.json"))
            if subcommand == "presets":
                rows = [f"{template.name}  {template.id}" for template in catalog.templates.values()
                        if template.faction == choice]
                if not rows:
                    raise ExperimentError("没有该阵营的预设，可选通用、东线、西线、南线")
                await self._reply(kwargs, "实验预设（用 /hd exp loadout <模板 ID> 抽取）\n" + "\n".join(rows))
                return True, "已发送实验预设", 2
            return await self._experimental_loadout(kwargs, group_id, catalog, choice)
        except KnowledgeError as exc:
            self._log("warning", "Experimental loadout knowledge is unavailable: %s", exc)
            message = "实验配装暂不可用，请管理员检查装备目录和标签表"
        except ExperimentError as exc:
            message = f"实验配装失败：{exc}"
        await self._reply(kwargs, message)
        return False, message, 2

    async def _experimental_loadout(
        self, kwargs: Mapping[str, Any], group_id: str, catalog: TemplateCatalog, choice: str,
    ) -> tuple[bool, str, int]:
        scope = group_id, self._loadout_scope(kwargs)
        now = time.monotonic()
        ttl = self._loadout_reroll_seconds()
        self._experimental_sessions = {
            key: session for key, session in self._experimental_sessions.items()
            if now - session.updated_at <= ttl
        }
        wants_reroll = choice.isdecimal() or choice in LOADOUT_INDEX_WORDS
        index = parse_loadout_index(choice) if wants_reroll and len(choice) <= 2 else 0
        session = self._experimental_sessions.get(scope)
        if wants_reroll:
            if index not in LOADOUT_SLOT_CHOICES:
                raise ExperimentError(f"重抽序号需要在 1-8 之间（{LOADOUT_SLOT_HINT}）")
            if session is None:
                raise ExperimentError(f"没有可重抽的实验配装，请先抽一套，重抽时限为 {ttl} 秒")

        knowledge = load_knowledge(
            self._knowledge_table(),
            self._data_file("loadout_knowledge.json"),
            self._data_file("loadout_data.json"),
        )
        if wants_reroll and session is not None:
            key = LOADOUT_SLOT_CHOICES[index]
            replacement = reroll_experimental_slot(knowledge, catalog, session.template_id, session.loadout, key)
            if replacement is None:
                raise ExperimentError(f"{loadout_slot_title(index)} 没有符合原模板的替代装备")
            session = replace(session, loadout={**session.loadout, key: replacement}, updated_at=now)
        else:
            template, loadout = generate_experimental_loadout(knowledge, catalog, choice)
            session = ExperimentalSession(template.id, template.name, loadout, now)

        self._experimental_sessions[scope] = session
        names = {key: knowledge.items[item_id].name for key, item_id in session.loadout.items()}
        return await self._send_loadout_card(kwargs, names, "", template_name=session.template_name)

    async def _reply(self, kwargs: Mapping[str, Any], message: str) -> bool:
        """Send command feedback to the originating chat stream.

        The host never delivers a command's returned ``response`` text to the
        chat, so every command must push its own reply through ``ctx.send.text``.
        """
        stream_id = str(kwargs.get("stream_id") or "").strip()
        if not stream_id:
            return False
        try:
            result = await self.ctx.send.text(text=message, stream_id=stream_id)
        except Exception as exc:  # a failed reply must not break the command
            self._log("warning", "Helldivers reply failed: %s", exc)
            return False
        if isinstance(result, Mapping):
            return bool(result.get("sent", result.get("success", False)))
        return result is not False


    @Command(
        COMMAND_NAME,
        description="随机配装、实验配装、单格重抽、状态与出图自检（/helldivers 或 /hd）",
        pattern=COMMAND_PATTERN,
        aliases=list(COMMAND_ALIASES),
        timeout_ms=COMMAND_RPC_TIMEOUT_MS,
        # MaiBot 1.4 gates ``permission="operator"`` commands on its own allow
        # lists before the handler runs. This component mixes public actions with
        # the admin-only ``diag``, so it stays public and keeps checking per
        # action itself; the host-side lists still apply on top.
        permission="public",
    )
    async def handle_command(self, **kwargs: Any) -> tuple[bool, str, int]:
        # 1.4 hands the live plugin config to every command; 1.3 does not.
        self._apply_command_config(kwargs)
        group_id = str(kwargs.get("group_id") or "").strip()
        if not group_id or group_id not in self._cfg_id_list("allowed_groups"):
            refusal = "本插件仅限配置白名单群聊使用"
            await self._reply(
                kwargs, f"{refusal}。请联系管理员在配置文件 plugin.allowed_groups 中添加群号。"
            )
            return False, refusal, 2
        action, argument = self._resolve_command(kwargs)
        if action == "exp":
            return await self._experimental_command(kwargs, group_id, argument)
        denial = self._command_permission(kwargs, action)
        if denial:
            await self._reply(kwargs, f"{denial}。")
            return False, denial, 2
        if not action:
            # The host only prefix-matches aliases, so this is text like ``/hdx`` that
            # the host claimed as a command but that our grammar cannot parse.
            text = str(kwargs.get("text") or "").strip()
            await self._reply(
                kwargs,
                f"没看懂「{text}」。触发词后面只接一个动作，例如 /hd st、/helldivers 状态。\n\n"
                f"{self._usage_hint()}",
            )
            return False, "命令格式无法解析", 2
        if action == "loadout":
            return await self._random_loadout(kwargs, argument)
        if action == "diag":
            return await self._diagnose(kwargs)
        if action == "help":
            await self._reply(kwargs, self._help_text(argument))
            return True, "已发送用法说明", 2
        if action != "status":
            message = f"未知子命令：{action}\n\n{self._usage_hint()}"
            await self._reply(kwargs, message)
            return False, f"未知子命令 {action}", 2
        pool = load_loadout_pool(self._data_file("loadout_data.json"))
        icons = load_loadout_icons(self._data_file("loadout_icons.json"))
        message = (
            "绝地潜兵 2：民主帮你选择\n"
            f"配装数据：{sum(len(names) for names in pool.values())} 件，图标 {len(icons)} 个\n"
            f"重抽时间窗：{self._loadout_reroll_seconds()} 秒\n"
            f"数据目录：{self._data_dir()}"
        )
        try:
            knowledge = load_knowledge(
                self._knowledge_table(),
                self._data_file("loadout_knowledge.json"),
                self._data_file("loadout_data.json"),
            )
            player_count = knowledge.player_tag_count
            edited_count = sum(item.user_modified for item in knowledge.items.values())
            message += f"\n配装标签：{len(knowledge.items)} 件，含玩家标签 {player_count} 件，标签修改 {edited_count} 件\n标签表：{knowledge.table_path.name}"
        except KnowledgeError as exc:
            message += "\n配装标签库暂不可用，请管理员检查 loadout_tags.xlsx 或 CSV"
            self._log("warning", "Loadout knowledge is unavailable: %s", exc)
        if self._last_render_error:
            message += f"\n配装出图异常：{self._last_render_error}（可用 /helldivers diag 复现）"
        await self._reply(kwargs, message)
        return True, "已发送状态", 2

    def _log(self, level: str, message: str, *args: Any) -> None:
        try:
            context = self.ctx
        except (AttributeError, RuntimeError):
            context = None
        logger = getattr(context, "logger", None)
        if logger and hasattr(logger, level):
            getattr(logger, level)(message, *args)


def parse_loadout_index(argument: str) -> int:
    """Card number from ``1``-``8``; ``0`` when the text is not a slot number."""
    text = str(argument or "").strip()
    if text.isdigit():
        return int(text)
    return LOADOUT_INDEX_WORDS.get(text, 0)


def loadout_slot_title(index: int) -> str:
    """Human name of a card number, e.g. ``5`` -> ``战略配备 1``."""
    key = LOADOUT_SLOT_CHOICES.get(index, "")
    if key.startswith("stratagem_"):
        return f"战略配备 {int(key.split('_')[1]) + 1}"
    return LOADOUT_SLOT_LABELS.get(key, key)


def reroll_loadout_slot(
    pool: Mapping[str, Sequence[str]],
    loadout: Mapping[str, str],
    key: str,
    rng: random.Random | None = None,
) -> str | None:
    """A different item for one card; ``None`` when the pool has no alternative."""
    picker = rng or random.Random()
    if key.startswith("stratagem_"):
        taken = {loadout.get(f"stratagem_{index}", "") for index in range(LOADOUT_STRATAGEM_COUNT)}
        candidates = [name for name in pool.get("stratagem", []) if name not in taken]
    else:
        current = loadout.get(key, "")
        candidates = [name for name in pool.get(key, []) if name != current]
    return picker.choice(candidates) if candidates else None


def resolve_data_dir(ctx: Any) -> Path:
    """The host-assigned per-instance data directory, or the bundled directory.

    MaiBot 1.4 passes ``ctx.paths.data_dir``; older hosts do not, and a plugin
    running outside a runner has no context at all. Both cases keep the previous
    behaviour: read the files shipped next to this module.
    """
    paths = getattr(ctx, "paths", None)
    raw = getattr(paths, "data_dir", None)
    if raw is None or not str(raw).strip():
        return BUNDLE_DIR
    try:
        return Path(raw)
    except (TypeError, ValueError):
        return BUNDLE_DIR


def data_file(name: str, data_dir: Path | None = None) -> Path:
    """Active copy of a data file: the per-instance one first, else the bundled one.

    ``EDITABLE_DATA_FILES`` are seeded into the data directory once so that an
    existing installation keeps its edits after the upgrade, and a later plugin
    update -- which replaces the source tree -- cannot drop them. A read-only or
    missing data directory simply falls back to the bundled file.
    """
    source = BUNDLE_DIR / name
    base = Path(data_dir) if data_dir is not None else BUNDLE_DIR
    if base == BUNDLE_DIR:
        return source
    target = base / name
    if target.exists():
        return target
    if name not in EDITABLE_DATA_FILES or not source.exists():
        return source
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    except OSError:
        return source
    return target


def load_loadout_pool(path: str | Path = LOADOUT_DATA_FILE) -> dict[str, list[str]]:
    """Slot -> item names. Returns an empty mapping when the data file is missing."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    items = payload.get("items") if isinstance(payload, Mapping) else None
    pool: dict[str, list[str]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, Mapping):
            continue
        slot = str(item.get("slot") or "")
        name = str(item.get("name") or "").strip()
        if slot and name:
            pool.setdefault(slot, []).append(name)
    return pool


def load_loadout_icons(path: str | Path = LOADOUT_ICONS_FILE) -> dict[str, str]:
    """Item name -> self-contained data URI. Empty when the icon file is absent.

    Cached per path: the file is several megabytes and the icon set does not
    change while the bot runs, but two instances (or a test run) can point at
    different files, so the cache cannot ignore ``path``.
    """
    global _LOADOUT_ICONS_CACHE, _LOADOUT_ICONS_CACHE_PATH
    target = Path(path)
    if _LOADOUT_ICONS_CACHE is None or _LOADOUT_ICONS_CACHE_PATH != target:
        icons: dict[str, str] = {}
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = None
        raw = payload.get("icons") if isinstance(payload, Mapping) else None
        if isinstance(raw, Mapping):
            for name, uri in raw.items():
                text = str(uri or "")
                if text.startswith("data:image/"):
                    icons[str(name)] = text
        _LOADOUT_ICONS_CACHE = icons
        _LOADOUT_ICONS_CACHE_PATH = target
    return _LOADOUT_ICONS_CACHE


def generate_loadout(
    pool: Mapping[str, Sequence[str]],
    rng: random.Random | None = None,
) -> dict[str, str]:
    """One item per ordinary slot plus four distinct stratagems."""
    picker = rng or random.Random()
    loadout: dict[str, str] = {}
    for slot in LOADOUT_SLOTS:
        choices = list(pool.get(slot) or [])
        if choices:
            loadout[slot] = picker.choice(choices)
    stratagems = list(pool.get("stratagem") or [])
    if stratagems:
        count = min(LOADOUT_STRATAGEM_COUNT, len(stratagems))
        for index, name in enumerate(picker.sample(stratagems, count)):
            loadout[f"stratagem_{index}"] = name
    return loadout


def render_loadout_html(
    loadout: Mapping[str, str],
    *,
    motto: str = "",
    footer: str = LOADOUT_FOOTER,
    icons: Mapping[str, str] | None = None,
) -> str:
    """Self-contained HTML card (no external assets) for ``ctx.render.html2png``.

    Icons are inlined as ``data:`` URIs; anything the icon file does not cover
    simply renders without a picture instead of breaking the card.
    """
    art = icons if icons is not None else {}

    def card(index: int, label: str, name: str) -> str:
        badge = f'<b class="idx">{index}</b>'
        if not name:
            return (
                f'<div class="card noicon"><div class="slot">{badge}{html.escape(label)}</div>'
                '<div class="name empty">没有可用装备</div></div>'
            )
        icon = art.get(name, "")
        # Escaped even though ``load_loadout_icons`` only admits ``data:image/``:
        # the value lands inside an HTML attribute, so it must not be able to
        # break out of it if the icon file is ever hand-edited.
        figure = f'<div class="icon"><img src="{html.escape(icon, quote=True)}" alt=""></div>' if icon else ""
        classes = "card" if icon else "card noicon"
        return (
            f'<div class="{classes}"><div class="slot">{badge}{html.escape(label)}</div>'
            f'{figure}<div class="name">{html.escape(name)}</div></div>'
        )

    ordinary = "".join(
        card(index, LOADOUT_SLOT_LABELS[slot], loadout.get(slot, ""))
        for index, slot in enumerate(LOADOUT_SLOTS, start=1)
    )
    stratagems = "".join(
        card(5 + index, "战略配备", loadout.get(f"stratagem_{index}", ""))
        for index in range(LOADOUT_STRATAGEM_COUNT)
    )
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><style>'
        "* { margin:0; padding:0; box-sizing:border-box; }"
        f"body {{ width:{LOADOUT_CARD_WIDTH}px; min-height:{LOADOUT_CARD_HEIGHT}px; padding:56px 55px; color:#f3f5f7;"
        "background:linear-gradient(180deg,#101720 0%,#090d13 55%,#05080c 100%);"
        'font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif; }'
        ".kicker { text-align:center; color:#f5cb3d; font-size:26px; font-weight:700; letter-spacing:4px; }"
        ".title { text-align:center; font-size:56px; font-weight:900; margin-top:10px; }"
        ".rule { height:3px; margin:32px 0; background:linear-gradient(90deg,transparent,#f5cb3d,transparent); }"
        ".section { color:#f5cb3d; font-size:32px; font-weight:800; margin:24px 0 18px; }"
        ".grid { display:grid; grid-template-columns:1fr 1fr; gap:26px; }"
        ".card { min-height:310px; padding:20px 22px; border-radius:24px; display:flex; flex-direction:column;"
        "background:rgba(18,25,34,.88); border:2px solid rgba(245,203,61,.55); }"
        ".slot { color:#f5cb3d; font-size:24px; font-weight:700; display:flex; align-items:center; gap:10px; }"
        ".idx { display:inline-flex; align-items:center; justify-content:center; flex:none; width:34px; height:34px;"
        "border-radius:50%; background:rgba(245,203,61,.16); border:2px solid rgba(245,203,61,.55); font-size:20px; }"
        ".icon { height:126px; margin:6px 0 10px; display:flex; align-items:center; justify-content:center; }"
        # width:auto keeps the img box on the artwork's own aspect ratio, which is what
        # lets border-radius actually clip the square tiles some icons ship with.
        ".icon img { height:100%; width:auto; max-width:100%; object-fit:contain; border-radius:12px; }"
        ".name { flex:1; display:flex; align-items:center; justify-content:center; text-align:center;"
        "font-size:34px; font-weight:700; line-height:1.22; word-break:break-word; }"
        ".noicon .name { font-size:40px; }"
        ".empty { color:#929aa4; font-size:28px; font-weight:400; }"
        ".motto { text-align:center; color:#f5cb3d; font-size:29px; font-weight:700; margin-top:42px; }"
        ".footer { text-align:center; color:#a7afb8; font-size:23px; margin-top:24px; }"
        "</style></head><body>"
        '<div class="kicker">为了超级地球</div>'
        '<div class="title">民主帮你选择</div>'
        '<div class="rule"></div>'
        '<div class="section">常规装备</div>'
        f'<div class="grid">{ordinary}</div>'
        '<div class="section">战略配备</div>'
        f'<div class="grid">{stratagems}</div>'
        f'<div class="motto">{html.escape(motto)}</div>'
        f'<div class="footer">{html.escape(footer)}</div>'
        "</body></html>"
    )


def format_loadout(loadout: Mapping[str, str], *, motto: str = "", template_name: str = "") -> str:
    """Plain-text rendering, used when the host cannot render images.

    Slot numbers match the badges on the card so a text-only user can reroll too.
    """
    mode = f"实验配装 · {template_name}" if template_name else "随机配装"
    lines = [f"【绝地潜兵 2：民主帮你选择·{mode}】"]
    for index, slot in enumerate(LOADOUT_SLOTS, start=1):
        if loadout.get(slot):
            lines.append(f"{index} {LOADOUT_SLOT_LABELS[slot]}：{loadout[slot]}")
    for index in range(LOADOUT_STRATAGEM_COUNT):
        name = loadout.get(f"stratagem_{index}", "")
        if name:
            lines.append(f"{5 + index} 战略配备：{name}")
    if motto:
        lines.append(motto)
    return "\n".join(lines)


def create_plugin() -> DemocracyChoosesPlugin:
    return DemocracyChoosesPlugin()
