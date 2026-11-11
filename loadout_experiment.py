"""Draw and reroll preset-based loadouts from the effective equipment tags."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
import json
from pathlib import Path
import random
import re
from typing import Mapping

if __package__:
    from .loadout_knowledge import EquipmentKnowledge, KnowledgeBase, SLOT_LABELS
else:
    from loadout_knowledge import EquipmentKnowledge, KnowledgeBase, SLOT_LABELS


_REGULAR_SLOTS = ("primary", "secondary", "grenade", "booster")
_STRATAGEM_SLOTS = tuple(f"stratagem_{index}" for index in range(4))
_SLOTS = (*_STRATAGEM_SLOTS, *_REGULAR_SLOTS)
_SLOT_COUNTS = {**dict.fromkeys(_REGULAR_SLOTS, 1), "stratagem": len(_STRATAGEM_SLOTS)}
_LIMITS = {"backpacks": 1, "persistent_support_weapons": 1, "temporary_support_weapons": 1, "vehicles": 1}
_FACTIONS = frozenset({"any", "terminids", "automatons", "illuminate"})

# Each of these may be occupied by at most one stratagem.
_BACKPACK, _PERSISTENT_SUPPORT, _TEMPORARY_SUPPORT, _VEHICLE = (1, 2, 4, 8)


class ExperimentError(ValueError):
    """An experimental preset could not be loaded, selected, or applied."""


@dataclass(frozen=True)
class SelectorClause:
    slots: frozenset[str]
    item_ids: frozenset[str]
    categories: frozenset[str]
    all_tags: frozenset[str]
    any_tags: frozenset[str]
    without_tags: frozenset[str]
    support_weapon: bool | None
    backpack: bool | None

    def matches(self, item: EquipmentKnowledge, tags: frozenset[str]) -> bool:
        return (
            (not self.slots or item.slot in self.slots)
            and (not self.item_ids or item.id in self.item_ids)
            and (not self.categories or item.category in self.categories)
            and (self.support_weapon is None or item.support_weapon is self.support_weapon)
            and (self.backpack is None or item.backpack is self.backpack)
            and self.all_tags <= tags
            and (not self.any_tags or not self.any_tags.isdisjoint(tags))
            and self.without_tags.isdisjoint(tags)
        )


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    faction: str
    mission: str
    summary: str
    requires: tuple[str, ...]
    stratagem_pool: tuple[str, ...]
    preferred: tuple[str, ...]
    allow_temporary_support: bool


@dataclass(frozen=True)
class TemplateCatalog:
    selectors: Mapping[str, tuple[SelectorClause, ...]]
    templates: Mapping[str, Template]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)


def _string_list(value: object, field: str) -> tuple[str, ...]:
    _require(isinstance(value, list) and all(isinstance(entry, str) and entry.strip() for entry in value),
             f"{field} 必须是字符串列表")
    _require(len(value) == len(set(value)), f"{field} 包含重复值")
    return tuple(value)


def _selector_clause(raw: object, selector: str) -> SelectorClause:
    list_fields = ("slots", "item_ids", "categories", "all_tags", "any_tags", "without_tags")
    bool_fields = ("support_weapon", "backpack")
    _require(isinstance(raw, dict) and bool(raw) and raw.keys() <= {*list_fields, *bool_fields},
             f"选择器 {selector} 的匹配分支无效")
    fields = {key: frozenset(_string_list(raw.get(key, []), f"{selector}.{key}")) for key in list_fields}
    _require(fields["slots"] <= SLOT_LABELS.keys(), f"选择器 {selector} 包含未知装备槽位")
    for key in bool_fields:
        _require(key not in raw or isinstance(raw[key], bool), f"{selector}.{key} 必须为布尔值")
        fields[key] = raw.get(key)
    return SelectorClause(**fields)


def load_templates(path: Path) -> TemplateCatalog:
    """Load the shipped preset schema and resolve its internal references."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExperimentError(f"配装预设读取失败：{exc}") from exc
    _require(isinstance(raw, dict) and raw.get("schema_version") == 1, "配装预设版本无效")
    _require(raw.get("slot_counts") == _SLOT_COUNTS and raw.get("limits") == _LIMITS, "配装槽位或携带上限无效")
    _require(isinstance(raw.get("selectors"), dict) and bool(raw["selectors"]), "配装预设缺少选择器")
    _require(isinstance(raw.get("templates"), list) and bool(raw["templates"]), "配装预设缺少模板")

    selectors = {}
    for key, selector in raw["selectors"].items():
        _require(isinstance(selector, dict) and isinstance(selector.get("match"), list) and bool(selector["match"]),
                 f"选择器 {key} 缺少匹配分支")
        selectors[key] = tuple(_selector_clause(clause, key) for clause in selector["match"])

    templates = {}
    for record in raw["templates"]:
        _require(isinstance(record, dict), "模板记录必须是对象")
        fields = {}
        for key in ("id", "name", "faction", "mission", "summary"):
            value = record.get(key)
            _require(isinstance(value, str) and bool(value.strip()), f"模板缺少有效的 {key}")
            fields[key] = value
        template_id = fields["id"]
        _require(re.fullmatch(r"[a-z][a-z0-9_-]*", template_id) is not None
                 and template_id not in templates and template_id not in _FACTIONS,
                 f"模板 ID 无效或重复：{template_id}")
        _require(fields["faction"] in _FACTIONS, f"模板 {template_id} 的战线无效")
        for key in ("requires", "stratagem_pool", "preferred"):
            values = _string_list(record.get(key, []), f"{template_id}.{key}")
            _require(key == "preferred" or bool(values), f"模板 {template_id} 缺少 {key}")
            for selector in values:
                _require(selector in selectors, f"模板 {template_id} 引用了未知选择器：{selector}")
            fields[key] = values
        allow_temporary = record.get("allow_temporary_support", False)
        _require(isinstance(allow_temporary, bool), f"模板 {template_id} 的临时支援开关必须为布尔值")
        templates[template_id] = Template(**fields, allow_temporary_support=allow_temporary)
    return TemplateCatalog(selectors, templates)


@dataclass(frozen=True)
class _Candidate:
    id: str
    covers: int
    usage: int
    shield: bool
    weight: int


def _candidates(knowledge: KnowledgeBase, catalog: TemplateCatalog, template: Template) -> tuple[dict[str, list[_Candidate]], int, int]:
    roles = {key: 1 << index for index, key in enumerate(template.requires)}
    one_handed = 1 << len(roles)
    required = one_handed - 1
    used_selectors = {key: catalog.selectors[key] for key in (*template.requires, *template.stratagem_pool, *template.preferred)}
    stratagem_pool = frozenset(template.stratagem_pool)
    preferred = frozenset(template.preferred)
    candidates = {key: [] for key in SLOT_LABELS}
    for item in knowledge.items.values():
        tags = item.tags
        matched = {key for key, clauses in used_selectors.items() if any(clause.matches(item, tags) for clause in clauses)}
        usage = 0
        if item.slot == "stratagem":
            if stratagem_pool.isdisjoint(matched) or item.support_weapon is None or item.backpack is None:
                continue
            if item.backpack:
                usage |= _BACKPACK
            if item.support_weapon:
                if "mechanic.expendable" in tags and not item.backpack:
                    if not template.allow_temporary_support:
                        continue
                    usage |= _TEMPORARY_SUPPORT
                else:
                    usage |= _PERSISTENT_SUPPORT
            if item.category == "vehicle":
                usage |= _VEHICLE
        covers = sum(roles[key] for key in roles.keys() & matched)
        if item.slot in {"primary", "secondary"} and "mechanic.one_handed" in tags:
            covers |= one_handed
        shield = item.slot == "stratagem" and "mechanic.requires_one_handed" in tags
        candidates[item.slot].append(_Candidate(item.id, covers, usage, shield, 1 + len(preferred & matched)))
    return candidates, required, one_handed


def _weighted_order(candidates: list[_Candidate], rng) -> list[_Candidate]:
    # Sampling without replacement, with every legal candidate retaining a chance.
    return sorted(candidates, key=lambda item: rng.random() ** (1 / item.weight), reverse=True)


def _coverage(candidates: list[_Candidate]) -> int:
    covered = 0
    for item in candidates:
        covered |= item.covers
    return covered


def _find_loadout(candidates: dict[str, list[_Candidate]], required: int, one_handed: int, rng) -> dict[str, str] | None:
    regular = [_weighted_order(candidates[slot], rng) for slot in _REGULAR_SLOTS]
    stratagems = _weighted_order(candidates["stratagem"], rng)
    regular_coverage = [0] * (len(regular) + 1)
    for index in reversed(range(len(regular))):
        regular_coverage[index] = regular_coverage[index + 1] | _coverage(regular[index])
    stratagem_coverage = [0] * (len(stratagems) + 1)
    for index in reversed(range(len(stratagems))):
        stratagem_coverage[index] = stratagem_coverage[index + 1] | stratagems[index].covers

    @cache
    def fill_regular(index: int, missing: int) -> tuple[str, ...] | None:
        if missing & ~regular_coverage[index]:
            return None
        if index == len(regular):
            return ()
        for item in regular[index]:
            tail = fill_regular(index + 1, missing & ~item.covers)
            if tail is not None:
                return (item.id, *tail)
        return None

    @cache
    def fill_stratagems(start: int, count: int, missing: int, usage: int) -> tuple[str, ...] | None:
        if count == 0:
            return fill_regular(0, missing)
        if missing & ~(stratagem_coverage[start] | regular_coverage[0]):
            return None
        # Increasing indices keep the four selections distinct and visit each set once.
        for index in range(start, len(stratagems) - count + 1):
            item = stratagems[index]
            if usage & item.usage:
                continue
            next_missing = missing & ~item.covers
            if item.shield:
                next_missing |= one_handed
            tail = fill_stratagems(index + 1, count - 1, next_missing, usage | item.usage)
            if tail is not None:
                return (item.id, *tail)
        return None

    result = fill_stratagems(0, len(_STRATAGEM_SLOTS), required, 0)
    if result is None:
        return None
    return dict(zip(_SLOTS, result))


def generate_experimental_loadout(
    knowledge: KnowledgeBase, catalog: TemplateCatalog, faction: str = "any", rng: random.Random | None = None,
) -> tuple[Template, dict[str, str]]:
    """Draw a feasible advancing preset for a front or select a specific preset by ID."""
    picker = rng if rng is not None else random
    selection = faction.strip().casefold() or "any"
    if selection in catalog.templates:
        templates = [catalog.templates[selection]]
    elif selection in _FACTIONS:
        templates = [t for t in catalog.templates.values() if t.faction == selection and t.mission == "advance"]
        picker.shuffle(templates)
    else:
        raise ExperimentError(f"未知战线或配装预设：{faction}")

    for template in templates:
        candidates, required, one_handed = _candidates(knowledge, catalog, template)
        loadout = _find_loadout(candidates, required, one_handed, picker)
        if loadout is not None:
            return template, loadout
    if selection in catalog.templates:
        raise ExperimentError(f"预设「{templates[0].name}」在当前装备标签下没有符合条件的八格配装")
    raise ExperimentError("这条战线的推进预设在当前装备标签下没有符合条件的八格配装")


def reroll_experimental_slot(
    knowledge: KnowledgeBase, catalog: TemplateCatalog, template_id: str, loadout: Mapping[str, str], key: str,
    rng: random.Random | None = None,
) -> str | None:
    """Return a different legal item for the specified slot with the other seven locked."""
    template = catalog.templates.get(template_id)
    _require(template is not None, "原配装预设已不可用，请重新抽取一套配装")
    _require(key in _SLOTS and set(loadout) == set(_SLOTS) and len(set(loadout.values())) == len(_SLOTS),
             "原配装槽位无效，请重新抽取一套配装")

    candidates, required, one_handed = _candidates(knowledge, catalog, template)
    by_slot = {slot: {item.id: item for item in pool} for slot, pool in candidates.items()}
    taken = set()
    covered = usage = 0
    shield = False
    invalid = "锁定的装备与当前预设或装备标签冲突，请重新抽取一套配装"
    for slot in _SLOTS:
        if slot == key:
            continue
        item = by_slot[slot.split("_")[0]].get(loadout[slot])
        _require(item is not None and not usage & item.usage, invalid)
        taken.add(item.id)
        covered |= item.covers
        usage |= item.usage
        shield |= item.shield

    alternatives = []
    original_valid = False
    for item in candidates[key.split("_")[0]]:
        needs = required | one_handed if shield or item.shield else required
        if item.id in taken or usage & item.usage or needs & ~(covered | item.covers):
            continue
        if item.id == loadout[key]:
            original_valid = True
        else:
            alternatives.append(item)

    if alternatives:
        picker = rng if rng is not None else random
        return picker.choices(alternatives, weights=[item.weight for item in alternatives], k=1)[0].id
    _require(original_valid, "当前装备标签下无法保留其余七格，请重新抽取一套配装")
    return None
