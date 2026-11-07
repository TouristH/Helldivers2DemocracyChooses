"""Read the editable CSV used by the loadout knowledge base, without networking."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
TABLE_PATH = ROOT / "loadout_tags.csv"
EVIDENCE_PATH = ROOT / "loadout_knowledge.json"
CATALOG_PATH = ROOT / "loadout_data.json"
CSV_FIELDS = (
    "id", "名称", "英文名", "槽位", "分类", "机制标签", "玩家定位", "玩家评价", "资料定位",
    "辅助标签", "反重便利性", "支援武器槽", "背包槽", "核实状态", "来源", "研究备注", "编辑说明",
)
SLOT_LABELS = {"primary": "主武器", "secondary": "副武器", "grenade": "投掷物", "booster": "强化资源", "stratagem": "战略配备"}
REVIEW_LABELS = {"verified": "已核实", "partial": "部分核实", "user_reviewed": "人工复核"}
EASE_LABELS = {"convenient": "方便", "conditional": "有条件", "emergency": "应急", "not_applicable": "不适用", "unknown": "待评价"}
BASES = {"wiki_fact", "official_fact", "community_observation", "curated_inference"}


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
    player_roles: frozenset[str]
    community_evaluations: frozenset[str]
    reference_roles: frozenset[str]
    utility: frozenset[str]
    anti_tank_ease: str
    support_weapon: bool | None
    backpack: bool | None
    review_status: str
    source_urls: str
    research_notes: str
    edit_notes: str
    user_modified: bool = False

    @property
    def tags(self) -> frozenset[str]:
        return self.mechanics | self.player_roles | self.community_evaluations | self.reference_roles | self.utility

    def role_basis(self, tag: str) -> str | None:
        """Community positioning wins for a role; mechanism tags stay independent."""
        if tag in self.player_roles:
            return "community_observation"
        if tag in self.reference_roles:
            return "reference"
        return None

    @property
    def prioritized_roles(self) -> tuple[str, ...]:
        return tuple(sorted(self.player_roles)) + tuple(sorted(self.reference_roles - self.player_roles))


@dataclass(frozen=True)
class KnowledgeBase:
    items: Mapping[str, EquipmentKnowledge]
    taxonomy: Mapping[str, Any]
    sources: Mapping[str, Any]
    research: Mapping[str, Any]

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
    _require(data.get("schema_version") == 1, "不支持的知识库版本")
    taxonomy = data["taxonomy"]
    tags, categories = taxonomy["tags"], taxonomy["categories"]
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
        refs = list(entry.get("category_source_ids", []))
        _require(bool(refs), f"分类缺少来源：{key}")
        claims = entry.get("tags", [])
        seen = set()
        for claim in claims:
            tag, basis = claim.get("id"), claim.get("basis")
            _require(tag in tags and basis in BASES, f"未知标签或依据：{key} / {tag}")
            _require((tag, basis) not in seen, f"重复标签依据：{key} / {tag}")
            _require(not tag.startswith("community.") or basis == "community_observation", f"玩家评价必须有社区依据：{key} / {tag}")
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
        for assessment in entry.get("community_assessments", []):
            _require(assessment.get("dimension") == "anti_tank_ease" and assessment.get("value") in EASE_LABELS, f"未知实战评价：{key}")
            assessment_refs = assessment.get("source_ids", [])
            _require(any(sources.get(ref, {}).get("kind") == "community" for ref in assessment_refs), f"实战便利性缺少社区来源：{key}")
            refs.extend(assessment_refs)
        _require(all(ref in sources for ref in refs), f"引用了不存在的来源：{key}")
        status = entry.get("review", {}).get("status")
        _require(status in {"verified", "partial"}, f"研究核实状态错误：{key}")
        if any(sources[ref]["access"] == "search_excerpt" for ref in refs):
            _require(status == "partial", f"仅有搜索摘要不能标为全文核实：{key}")


def _label_map(definitions: Mapping[str, Any]) -> dict[str, str]:
    return {key: key for key in definitions} | {value["label"]: key for key, value in definitions.items()}


def _tokens(value: str, definitions: Mapping[str, Any], dimension: str) -> frozenset[str]:
    aliases = _label_map(definitions)
    values = [token.strip() for token in value.split("|") if token.strip()]
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
    players = frozenset(c["id"] for c in claims if c["id"].startswith("role.") and c["basis"] == "community_observation")
    evaluations = frozenset(c["id"] for c in claims if c["id"].startswith("community."))
    references = frozenset(c["id"] for c in claims if c["id"].startswith("role.") and c["basis"] != "community_observation")
    utility = frozenset(c["id"] for c in claims if not c["id"].startswith(("mechanic.", "role.", "community.")))
    assessments = entry.get("community_assessments", [])
    # Disagreeing experiences remain undecided instead of selecting a winner.
    values = {a["value"] for a in assessments}
    ease = next(iter(values)) if len(values) == 1 else "unknown"
    return (entry["category"], mechanics, players, evaluations, references, utility, ease, entry["occupancy"].get("support_weapon"), entry["occupancy"].get("backpack"))


def load_knowledge(table_path: Path = TABLE_PATH, evidence_path: Path = EVIDENCE_PATH, catalog_path: Path = CATALOG_PATH) -> KnowledgeBase:
    """Read CSV on each call so saved edits take effect without regenerating JSON."""
    try:
        evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
        validate_evidence(evidence, catalog)
        taxonomy = evidence["taxonomy"]
        tags, categories = taxonomy["tags"], taxonomy["categories"]
        catalog_items = _index(catalog["items"], "装备目录")
        research = _index(evidence["items"], "研究记录")
        category_aliases = _label_map(categories)
        rows = csv.DictReader(io.StringIO(Path(table_path).read_text(encoding="utf-8-sig")))
        _require(tuple(rows.fieldnames or []) == CSV_FIELDS, "CSV 列名或顺序不匹配，请保留原表头")
        result = {}
        for row in rows:
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
                players = _tokens(row["玩家定位"], tags, "role")
                evaluations = _tokens(row["玩家评价"], tags, "community")
                references = _tokens(row["资料定位"], tags, "role")
                utility = _tokens(row["辅助标签"], tags, "auxiliary")
                ease_aliases = {v: k for k, v in EASE_LABELS.items()} | {k: k for k in EASE_LABELS}
                review_aliases = {v: k for k, v in REVIEW_LABELS.items()} | {k: k for k in REVIEW_LABELS}
                _require(row["反重便利性"] in ease_aliases, "反重便利性请填：方便/有条件/应急/不适用/待评价")
                _require(row["核实状态"] in review_aliases, "核实状态请填：已核实/部分核实/人工复核")
                support, backpack = _occupancy(row["支援武器槽"]), _occupancy(row["背包槽"])
                if item["slot"] != "stratagem":
                    _require(support is False and backpack is False, "常规装备不能标为占用支援武器或背包槽")
                ease = ease_aliases[row["反重便利性"]]
                edited = (category, mechanics, players, evaluations, references, utility, ease, support, backpack) != _baseline(research[key])
                result[key] = EquipmentKnowledge(key, item["name"], item["name_en"], item["slot"], category, mechanics, players, evaluations, references, utility, ease, support, backpack, review_aliases[row["核实状态"]], row["来源"], row["研究备注"], row["编辑说明"], edited)
            except KnowledgeError as exc:
                raise KnowledgeError(f"CSV 第 {rows.line_num} 行（{key or '无 id'}）：{exc}") from exc
        _require(set(result) == set(catalog_items), f"CSV 装备缺失：{'、'.join(sorted(set(catalog_items) - set(result))[:5])}")
        return KnowledgeBase(result, taxonomy, _index(evidence["sources"], "来源"), research)
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error, KeyError, TypeError, AttributeError) as exc:
        raise KnowledgeError(f"知识库读取失败：{exc}") from exc
