"""Coverage, provenance, and direct-edit behavior of the equipment knowledge table."""
import copy
import csv
import io
import json
from pathlib import Path

import pytest

from loadout_knowledge import (
    CATALOG_PATH, CSV_FIELDS, EVIDENCE_PATH, KnowledgeError, PLAYER_TAG_DEFINITIONS, TABLE_PATH,
    load_knowledge, validate_evidence,
)


def table_rows():
    return list(csv.DictReader(io.StringIO(TABLE_PATH.read_text(encoding="utf-8-sig"))))


def edited_table(tmp_path: Path, rows):
    path = tmp_path / "edited.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_every_catalog_item_is_in_the_editable_table():
    knowledge = load_knowledge()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert set(knowledge.items) == {item["id"] for item in catalog["items"]}
    assert len(knowledge.items) == 221


def test_schema_uses_the_fixed_atomic_player_vocabulary():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert evidence["schema_version"] == 2
    definitions = {
        key: value for key, value in evidence["taxonomy"]["tags"].items()
        if value["dimension"] == "player"
    }
    assert len(definitions) == 25
    assert definitions.keys() == PLAYER_TAG_DEFINITIONS.keys()
    assert {key: value["label"] for key, value in definitions.items()} == {
        key: value["label"] for key, value in PLAYER_TAG_DEFINITIONS.items()
    }
    assert CSV_FIELDS == (
        "id", "名称", "英文名", "槽位", "分类", "机制标签", "玩家标签集", "资料定位",
        "辅助标签", "支援武器槽", "背包槽", "核实状态", "来源", "研究备注", "编辑说明",
    )


@pytest.mark.parametrize("change", ["missing", "extra", "renamed"])
def test_player_vocabulary_cannot_be_removed_expanded_or_renamed(change):
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    tags = evidence["taxonomy"]["tags"]
    if change == "missing":
        tags.pop("player.toy")
    elif change == "extra":
        tags["player.combined"] = {"dimension": "player", "label": "组合玩家标签", "description": ""}
    else:
        tags["player.toy"]["label"] = "任意改名"
    with pytest.raises(KnowledgeError, match="固定"):
        validate_evidence(evidence, json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def test_csv_edit_takes_effect_without_rebuilding_json(tmp_path):
    evidence_before = EVIDENCE_PATH.read_bytes()
    rows = table_rows()
    row = rows[0]
    row["玩家标签集"] = "控场；清杂；易误伤"
    row["编辑说明"] = "人工补充：保留独立玩家标签"
    table = edited_table(tmp_path, rows)
    first = load_knowledge(table).items[row["id"]]
    assert first.player_tags == frozenset({"player.crowd_control", "player.crowd_clear", "player.friendly_fire_risk"})
    row["玩家标签集"] = "反重；简易使用；对单"
    edited_table(tmp_path, rows)
    second = load_knowledge(table).items[row["id"]]
    assert second.player_tags == frozenset({"player.anti_tank", "player.easy_to_use", "player.single_target"})
    assert first.user_modified or second.user_modified
    assert EVIDENCE_PATH.read_bytes() == evidence_before


@pytest.mark.parametrize("value, expected, display", [
    ("控场；清杂；易误伤", {"player.crowd_control", "player.crowd_clear", "player.friendly_fire_risk"}, "控场；清杂；易误伤"),
    ("控场;清杂;易误伤", {"player.crowd_control", "player.crowd_clear", "player.friendly_fire_risk"}, "控场；清杂；易误伤"),
    ("player.crowd_control|player.crowd_clear|player.friendly_fire_risk", {"player.crowd_control", "player.crowd_clear", "player.friendly_fire_risk"}, "控场；清杂；易误伤"),
    (" 控场 | player.crowd_clear；清杂;易误伤；player.crowd_control ", {"player.crowd_control", "player.crowd_clear", "player.friendly_fire_risk"}, "控场；清杂；易误伤"),
    ("反重；简易使用；对单", {"player.anti_tank", "player.easy_to_use", "player.single_target"}, "反重；简易使用；对单"),
])
def test_player_tag_sets_accept_names_ids_and_separators_without_combining_tags(tmp_path, value, expected, display):
    rows = table_rows()
    rows[0]["玩家标签集"] = value
    item = load_knowledge(edited_table(tmp_path, rows)).items[rows[0]["id"]]
    assert isinstance(item.player_tags, frozenset)
    assert item.player_tags == frozenset(expected)
    assert len(item.player_tags) == 3
    assert item.player_tags <= PLAYER_TAG_DEFINITIONS.keys()
    assert item.player_tag_display == display
    assert all(item.tag_basis(tag) == "community_observation" for tag in expected)


def test_player_positioning_and_mechanism_facts_coexist(tmp_path):
    rows = table_rows()
    rows[0]["玩家标签集"] = "player.anti_tank；玩具；评价有分歧"
    rows[0]["资料定位"] = "role.anti_tank"
    rows[0]["机制标签"] = "mechanic.ballistic|mechanic.heavy_penetration_trait"
    item = load_knowledge(edited_table(tmp_path, rows)).items[rows[0]["id"]]
    assert item.player_tags == frozenset({"player.anti_tank", "player.toy", "player.disputed"})
    assert item.tag_basis("player.anti_tank") == "community_observation"
    assert item.tag_basis("role.anti_tank") == "reference"
    assert "role.anti_tank" in item.reference_roles
    assert "mechanic.ballistic" in item.mechanics
    assert "mechanic.heavy_penetration_trait" in item.mechanics
    assert item.player_tag_display == "反重；玩具；评价有分歧"
    assert item.player_tags | item.reference_roles | item.mechanics <= item.tags
    for removed in ("player_roles", "community_evaluations", "anti_tank_ease", "prioritized_roles"):
        assert not hasattr(item, removed)


def test_heavy_penetration_and_reference_roles_do_not_infer_player_anti_tank(tmp_path):
    rows = table_rows()
    rows[0]["玩家标签集"] = ""
    rows[0]["资料定位"] = "role.anti_tank"
    rows[0]["机制标签"] = "mechanic.heavy_penetration_trait"
    item = load_knowledge(edited_table(tmp_path, rows)).items[rows[0]["id"]]
    assert item.player_tags == frozenset()
    assert item.player_tag_display == ""
    assert "mechanic.heavy_penetration_trait" in item.mechanics
    assert "role.anti_tank" in item.reference_roles
    assert "player.anti_tank" not in item.tags
    assert item.tag_basis("player.anti_tank") is None


@pytest.mark.parametrize("change", ["duplicate", "missing", "wrong_slot"])
def test_invalid_table_is_rejected_with_a_useful_error(tmp_path, change):
    rows = table_rows()
    if change == "duplicate":
        rows.append(dict(rows[0]))
    elif change == "missing":
        rows.pop()
    else:
        next(row for row in rows if row["槽位"] in {"主武器", "primary"})["背包槽"] = "是"
    with pytest.raises(KnowledgeError):
        load_knowledge(edited_table(tmp_path, rows))


@pytest.mark.parametrize("column, value", [
    ("玩家标签集", "player.does_not_exist"),
    ("玩家标签集", "未知玩家标签"),
    ("玩家标签集", "player.anti_tank_easy_to_use_single_target"),
    ("玩家标签集", "role.anti_tank"),
    ("玩家标签集", "mechanic.heavy_penetration_trait"),
    ("机制标签", "player.anti_tank"),
    ("机制标签", "role.anti_tank"),
    ("资料定位", "player.anti_tank"),
    ("辅助标签", "player.toy"),
])
def test_unknown_or_wrong_dimension_tags_are_rejected(tmp_path, column, value):
    rows = table_rows()
    rows[0][column] = value
    with pytest.raises(KnowledgeError, match="未知标签|不属于此列"):
        load_knowledge(edited_table(tmp_path, rows))


def test_community_claim_cannot_be_supported_only_by_a_wiki_source():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    evidence = copy.deepcopy(evidence)
    wiki = next(source["id"] for source in evidence["sources"] if source["kind"] == "wiki")
    entry = evidence["items"][0]
    entry["tags"] = [claim for claim in entry["tags"] if claim["id"] != "player.anti_tank"]
    entry["tags"].append({"id": "player.anti_tank", "basis": "community_observation", "source_ids": [wiki]})
    with pytest.raises(KnowledgeError, match="社区来源"):
        validate_evidence(evidence, json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def test_search_excerpt_cannot_be_claimed_as_full_verification():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    excerpt = next(source["id"] for source in evidence["sources"] if source["access"] == "search_excerpt")
    evidence["items"][0]["category_source_ids"].append(excerpt)
    evidence["items"][0]["review"]["status"] = "verified"
    with pytest.raises(KnowledgeError, match="搜索摘要"):
        validate_evidence(evidence, json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize("invalid", [None, [], {"schema_version": 1, "taxonomy": None}, {"schema_version": 2, "taxonomy": None}])
def test_malformed_json_is_a_recoverable_knowledge_error(tmp_path, invalid):
    evidence_path = tmp_path / "broken.json"
    evidence_path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(KnowledgeError):
        load_knowledge(evidence_path=evidence_path)


def test_invalid_json_syntax_is_a_recoverable_knowledge_error(tmp_path):
    evidence_path = tmp_path / "broken.json"
    evidence_path.write_text('{"schema_version": 2,', encoding="utf-8")
    with pytest.raises(KnowledgeError):
        load_knowledge(evidence_path=evidence_path)
