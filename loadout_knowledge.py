"""Read editable Excel/CSV equipment knowledge without networking or dependencies."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

if __package__:
    from .knowledge_workbook import WorkbookError, read_workbook_rows
else:
    from knowledge_workbook import WorkbookError, read_workbook_rows

ROOT = Path(__file__).resolve().parent
TABLE_PATH = ROOT / "loadout_tags.csv"
WORKBOOK_PATH = ROOT / "loadout_tags.xlsx"
EVIDENCE_PATH = ROOT / "loadout_knowledge.json"
CATALOG_PATH = ROOT / "loadout_data.json"
CSV_FIELDS = (
    "id", "名称", "英文名", "槽位", "分类", "机制标签", "玩家标签集", "资料定位",
    "辅助标签", "支援武器槽", "背包槽", "核实状态", "来源", "研究备注", "编辑说明",
)
SLOT_LABELS = {"primary": "主武器", "secondary": "副武器", "grenade": "投掷物", "booster": "强化资源", "stratagem": "战略配备"}
REVIEW_LABELS = {"verified": "已核实", "partial": "部分核实", "user_reviewed": "人工复核"}
BASES = {"wiki_fact", "official_fact", "community_observation", "curated_inference"}
_PLAYER_TAG_ROWS = (
    ("anti_tank", "反重", "玩家反馈可承担重型威胁处理；适用目标与条件见研究备注。"),
    ("anti_medium", "反中", "处理中型威胁的玩家定位，不由穿甲等级自动生成。"),
    ("anti_air", "对空", "有玩家实战依据的对空用途。"),
    ("crowd_control", "控场", "通过眩晕、错乱、硬直等限制敌人行动。"),
    ("crowd_clear", "清杂", "适合清理轻型敌群的玩家定位。"),
    ("structure_demolition", "拆迁", "有玩家依据的生成点或设施处理用途，具体对象见备注。"),
    ("area_denial", "区域封锁", "持续影响区域、限制敌方通行或驻留。"),
    ("sustain", "续航支援", "补给或治疗等续航支援用途。"),
    ("protection", "防护", "玩家认可的减伤、挡弹或掩护用途。"),
    ("mobility", "机动", "帮助移动、转移或接近目标。"),
    ("stealth", "潜行", "有实际隐蔽或脱战反馈，不将出现在潜行配装中等同无声属性。"),
    ("objective_support", "任务辅助", "对样本、撤离、增援等任务流程有帮助。"),
    ("easy_to_use", "简易使用", "玩家在备注场景中认为操作直观或命中要求较宽容，不保证无条件有效。"),
    ("precise_aim_required", "需精确瞄准", "较依赖弱点或精确命中，适用目标与距离见备注。"),
    ("preparation_required", "需准备", "发挥依赖蓄力、架设、等待或合适站位等准备条件。"),
    ("supply_dependent", "补给依赖", "玩家明确指出弹量或持续作战对补给的依赖。"),
    ("single_target", "对单", "有明确单个或指定目标的实战定位，不由反重标签自动推导。"),
    ("area_target", "对群", "有明确多目标或范围作战反馈，不由清杂标签自动推导。"),
    ("friendly_fire_risk", "易误伤", "玩家明确讨论的友军误伤风险。"),
    ("self_damage_risk", "易自伤", "玩家明确讨论的自伤风险。"),
    ("emergency_backup", "应急补位", "在备注所述目标或场景中更适合作为补充，不等于整件装备只能应急。"),
    ("toy", "玩具", "部分玩家认为偏整活、角色扮演或耍帅，保留实用反例，不等于完全无效。"),
    ("disputed", "评价有分歧", "存在不同玩家体验或不同条件下的相反反馈，具体内容见备注。"),
    ("automaton_recommended", "机器人推荐", "玩家机器人战线配装推荐，不是通用强度评级。"),
    ("illuminate_recommended", "光能族推荐", "玩家光能族战线配装推荐，不是通用强度评级。"),
)
PLAYER_TAG_DEFINITIONS = {
    f"player.{key}": {"label": label, "description": description, "dimension": "player"}
    for key, label, description in _PLAYER_TAG_ROWS
}


def format_player_tags(tags: frozenset[str]) -> str:
    """Join atomic IDs for review only; the joined text is never a tag ID."""
    _require(set(tags) <= PLAYER_TAG_DEFINITIONS.keys(), "玩家标签不在固定词表内")
    return "；".join(definition["label"] for key, definition in PLAYER_TAG_DEFINITIONS.items() if key in tags)


class KnowledgeError(ValueError):
    """An invalid table must not silently become valid-looking equipment data."""


@dataclass(frozen=True)
class EquipmentKnowledge:
    id: str
    name: str
    name_en: str
    slot: str
    category: str
    mechanics: frozenset[str]
    player_tags: frozenset[str]
    reference_roles: frozenset[str]
    utility: frozenset[str]
    support_weapon: bool | None
    backpack: bool | None
    review_status: str
    source_urls: str
    research_notes: str
    edit_notes: str
    user_modified: bool = False

    @property
    def tags(self) -> frozenset[str]:
        return self.mechanics | self.player_tags | self.reference_roles | self.utility

    def tag_basis(self, tag: str) -> str | None:
        if tag in self.player_tags:
            return "community_observation"
        if tag in self.reference_roles:
            return "reference"
        return None

    @property
    def player_tag_display(self) -> str:
        return format_player_tags(self.player_tags)


@dataclass(frozen=True)
class KnowledgeBase:
    items: Mapping[str, EquipmentKnowledge]
    taxonomy: Mapping[str, Any]
    sources: Mapping[str, Any]
    research: Mapping[str, Any]
    table_path: Path

    @property
    def player_tag_count(self) -> int:
        return sum(bool(item.player_tags) for item in self.items.values())

    def find(self, name_or_id: str) -> EquipmentKnowledge | None:
        key = name_or_id.strip().casefold()
        return next((item for item in self.items.values() if key in (item.id.casefold(), item.name.casefold(), item.name_en.casefold())), None)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise KnowledgeError(message)


def _index(records: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    _require(isinstance(records, list), f"{label}应为列表")
    result = {}
    for record in records:
        _require(isinstance(record, Mapping), f"{label}记录应为对象")
        key = record.get("id")
        _require(isinstance(key, str) and bool(key), f"{label} 缺少 id")
        _require(key not in result, f"{label} id 重复：{key}")
        result[key] = record
    return result


def validate_evidence(data: Mapping[str, Any], catalog: Mapping[str, Any]) -> None:
    """Validate coverage and provenance, including facts versus player observations."""
    _require(isinstance(data, Mapping) and isinstance(catalog, Mapping), "知识库和装备目录应为 JSON 对象")
    _require(data.get("schema_version") == 2, "不支持的知识库版本，请使用配套的新标签表")
    taxonomy = data["taxonomy"]
    tags, categories = taxonomy["tags"], taxonomy["categories"]
    player_definitions = {key: value for key, value in tags.items() if value.get("dimension") == "player"}
    _require(player_definitions.keys() == PLAYER_TAG_DEFINITIONS.keys(), "玩家标签必须使用固定的独立标签词表")
    _require(all(player_definitions[key]["label"] == value["label"] for key, value in PLAYER_TAG_DEFINITIONS.items()), "玩家标签名称与固定词表不一致")
    _require(tuple(taxonomy.get("player_tag_order", [])) == tuple(PLAYER_TAG_DEFINITIONS), "玩家标签显示顺序与固定词表不一致")
    sources = _index(data["sources"], "来源")
    entries = _index(data["items"], "研究记录")
    catalog_items = _index(catalog["items"], "装备目录")
    _require(set(entries) == set(catalog_items), "研究记录与装备目录 id 不一致")
    for source in sources.values():
        _require(source.get("kind") in {"wiki", "official", "community"}, f"来源类型错误：{source['id']}")
        _require(str(source.get("url", "")).startswith("https://"), f"来源必须使用 HTTPS：{source['id']}")
        _require(source.get("access") in {"page", "search_excerpt"}, f"来源查阅方式错误：{source['id']}")
    for key, entry in entries.items():
        _require(entry["slot"] == catalog_items[key]["slot"] and entry["name_en"] == catalog_items[key]["name_en"], f"装备身份不匹配：{key}")
        _require(entry.get("category") in categories, f"未知分类：{key}")
        _require("community_assessments" not in entry, f"旧版单独评价字段未迁移：{key}")
        refs = list(entry.get("category_source_ids", []))
        _require(bool(refs), f"分类缺少来源：{key}")
        claims = entry.get("tags", [])
        seen = set()
        for claim in claims:
            tag, basis = claim.get("id"), claim.get("basis")
            _require(tag in tags and basis in BASES, f"未知标签或依据：{key} / {tag}")
            _require((tag, basis) not in seen, f"重复标签依据：{key} / {tag}")
            _require(not tag.startswith("player.") or (tag in PLAYER_TAG_DEFINITIONS and basis == "community_observation"), f"玩家标签必须有社区依据：{key} / {tag}")
            _require(not (tag.startswith("role.") and basis == "community_observation"), f"玩家职责尚未规范为独立玩家标签：{key} / {tag}")
            seen.add((tag, basis))
            claim_refs = claim.get("source_ids", [])
            _require(bool(claim_refs), f"标签缺少来源：{key} / {tag}")
            refs.extend(claim_refs)
            if basis == "community_observation":
                _require(any(sources.get(ref, {}).get("kind") == "community" for ref in claim_refs), f"玩家定位缺少社区来源：{key} / {tag}")
            elif basis in {"wiki_fact", "official_fact"}:
                kind = "wiki" if basis == "wiki_fact" else "official"
                _require(any(sources.get(ref, {}).get("kind") == kind for ref in claim_refs), f"资料依据类型不符：{key} / {tag}")
        occupancy = entry.get("occupancy", {})
        for field in ("support_weapon", "backpack"):
            value = occupancy.get(field)
            _require(value is None or type(value) is bool, f"槽位占用应为 true/false/null：{key} / {field}")
        refs.extend(occupancy.get("source_ids", []))
        for observation in entry.get("observations", []):
            observation_refs = observation.get("source_ids", [])
            _require(any(sources.get(ref, {}).get("kind") == "community" for ref in observation_refs), f"实战补充缺少社区来源：{key}")
            refs.extend(observation_refs)
        _require(all(ref in sources for ref in refs), f"引用了不存在的来源：{key}")
        status = entry.get("review", {}).get("status")
        _require(status in {"verified", "partial"}, f"研究核实状态错误：{key}")
        if any(sources[ref]["access"] == "search_excerpt" for ref in refs):
            _require(status == "partial", f"仅有搜索摘要不能标为全文核实：{key}")


def _label_map(definitions: Mapping[str, Any]) -> dict[str, str]:
    return {key: key for key in definitions} | {value["label"]: key for key, value in definitions.items()}


def _tokens(value: str, definitions: Mapping[str, Any], dimension: str) -> frozenset[str]:
    scoped = {key: definition for key, definition in definitions.items() if definition["dimension"] == dimension}
    aliases = _label_map(scoped)
    values = [token.strip() for token in re.split(r"[；;|、\n]+", value) if token.strip()]
    for token in values:
        _require(token in aliases, f"未知标签「{token}」，请查阅标签字典")
        _require(definitions[aliases[token]]["dimension"] == dimension, f"「{token}」不属于此列")
    return frozenset(aliases[token] for token in values)


def _occupancy(value: str) -> bool | None:
    choices = {"是": True, "否": False, "待核实": None, "": None, "true": True, "false": False, "1": True, "0": False}
    _require(value.casefold() in choices, f"槽位占用请填「是」「否」或「待核实」：{value}")
    return choices[value.casefold()]


def _baseline(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    claims = entry.get("tags", [])
    mechanics = frozenset(c["id"] for c in claims if c["id"].startswith("mechanic."))
    players = frozenset(c["id"] for c in claims if c["id"].startswith("player."))
    references = frozenset(c["id"] for c in claims if c["id"].startswith("role."))
    utility = frozenset(c["id"] for c in claims if not c["id"].startswith(("mechanic.", "role.", "player.")))
    return (entry["category"], mechanics, players, references, utility, entry["occupancy"].get("support_weapon"), entry["occupancy"].get("backpack"))


def selected_table_path(table_path: Path | None = None) -> Path:
    return Path(table_path) if table_path is not None else WORKBOOK_PATH if WORKBOOK_PATH.exists() else TABLE_PATH


def load_knowledge(table_path: Path | None = None, evidence_path: Path = EVIDENCE_PATH, catalog_path: Path = CATALOG_PATH) -> KnowledgeBase:
    """Prefer Excel when present; explicitly passed CSV paths remain supported."""
    try:
        evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
        validate_evidence(evidence, catalog)
        taxonomy = evidence["taxonomy"]
        tags, categories = taxonomy["tags"], taxonomy["categories"]
        catalog_items = _index(catalog["items"], "装备目录")
        research = _index(evidence["items"], "研究记录")
        category_aliases = _label_map(categories)
        path = selected_table_path(table_path)
        if path.suffix.casefold() == ".xlsx":
            records = enumerate(read_workbook_rows(path, CSV_FIELDS), start=2)
        else:
            _require(path.suffix.casefold() == ".csv", "标签表仅支持 .xlsx 或 .csv")
            rows = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))
            _require(tuple(rows.fieldnames or []) == CSV_FIELDS, "CSV 列名或顺序不匹配，请保留原表头")
            records = ((rows.line_num, row) for row in rows)
        result = {}
        for row_number, row in records:
            if not any(value for value in row.values()):
                continue
            key = (row.get("id") or "").strip()
            try:
                _require(None not in row and all(value is not None for value in row.values()), "列数不匹配")
                row = {field: value.strip() for field, value in row.items()}
                _require(key in catalog_items and key not in result, "id 不存在或重复")
                item = catalog_items[key]
                _require(row["名称"] == item["name"] and row["英文名"] == item["name_en"], "请勿修改装备名称或英文名")
                _require(row["槽位"] in {item["slot"], SLOT_LABELS[item["slot"]]}, "请勿修改装备槽位")
                _require(row["分类"] in category_aliases, f"未知分类：{row['分类']}")
                category = category_aliases[row["分类"]]
                mechanics = _tokens(row["机制标签"], tags, "mechanic")
                players = _tokens(row["玩家标签集"], tags, "player")
                references = _tokens(row["资料定位"], tags, "role")
                utility = _tokens(row["辅助标签"], tags, "auxiliary")
                review_aliases = {v: k for k, v in REVIEW_LABELS.items()} | {k: k for k in REVIEW_LABELS}
                _require(row["核实状态"] in review_aliases, "核实状态请填：已核实/部分核实/人工复核")
                support, backpack = _occupancy(row["支援武器槽"]), _occupancy(row["背包槽"])
                if item["slot"] != "stratagem":
                    _require(support is False and backpack is False, "常规装备不能标为占用支援武器或背包槽")
                edited = (category, mechanics, players, references, utility, support, backpack) != _baseline(research[key])
                result[key] = EquipmentKnowledge(key, item["name"], item["name_en"], item["slot"], category, mechanics, players, references, utility, support, backpack, review_aliases[row["核实状态"]], row["来源"], row["研究备注"], row["编辑说明"], edited)
            except KnowledgeError as exc:
                raise KnowledgeError(f"{path.name} 第 {row_number} 条记录（{key or '无 id'}）：{exc}") from exc
        _require(set(result) == set(catalog_items), f"标签表装备缺失：{'、'.join(sorted(set(catalog_items) - set(result))[:5])}")
        return KnowledgeBase(result, taxonomy, _index(evidence["sources"], "来源"), research, path)
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error, KeyError, TypeError, AttributeError, WorkbookError) as exc:
        raise KnowledgeError(f"知识库读取失败：{exc}") from exc


def export_csv(knowledge: KnowledgeBase, destination: Path) -> Path:
    """Export the validated effective workbook/table to the canonical CSV columns."""
    destination = Path(destination)
    _require(destination.suffix.casefold() == ".csv", "导出文件请使用 .csv 后缀")
    tags, categories = knowledge.taxonomy["tags"], knowledge.taxonomy["categories"]
    labels = lambda values: "|".join(tags[key]["label"] for key in sorted(values))
    occupied = lambda value: "待核实" if value is None else "是" if value else "否"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=destination.parent, prefix=".knowledge-", suffix=".csv", delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
            writer.writeheader()
            for item in knowledge.items.values():
                writer.writerow(dict(zip(CSV_FIELDS, (
                    item.id, item.name, item.name_en, SLOT_LABELS[item.slot], categories[item.category]["label"],
                    labels(item.mechanics), item.player_tag_display,
                    labels(item.reference_roles), labels(item.utility),
                    occupied(item.support_weapon), occupied(item.backpack), REVIEW_LABELS[item.review_status],
                    item.source_urls, item.research_notes, item.edit_notes,
                ))))
        os.replace(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
