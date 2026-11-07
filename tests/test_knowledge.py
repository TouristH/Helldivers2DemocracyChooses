"""Coverage, provenance, and direct-edit behavior of the equipment knowledge table."""
import copy
import csv
import io
import json
from pathlib import Path

import pytest

from loadout_knowledge import (
    CATALOG_PATH, CSV_FIELDS, EVIDENCE_PATH, KnowledgeError, TABLE_PATH,
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


def test_csv_edit_takes_effect_without_rebuilding_json(tmp_path):
    evidence_before = EVIDENCE_PATH.read_bytes()
    rows = table_rows()
    row = rows[0]
    row["玩家定位"] = "role.anti_tank"
    row["反重便利性"] = "有条件"
    row["编辑说明"] = "人工补充：要求瞄准指定弱点"
    table = edited_table(tmp_path, rows)
    item = load_knowledge(table).items[row["id"]]
    assert item.player_roles == frozenset({"role.anti_tank"})
    assert item.anti_tank_ease == "conditional"
    assert item.user_modified
    assert EVIDENCE_PATH.read_bytes() == evidence_before
    row["反重便利性"] = "应急"
    edited_table(tmp_path, rows)
    assert load_knowledge(table).items[row["id"]].anti_tank_ease == "emergency"


def test_player_positioning_and_mechanism_facts_coexist(tmp_path):
    rows = table_rows()
    rows[0]["玩家定位"] = rows[0]["资料定位"] = "role.anti_tank"
    rows[0]["机制标签"] = "mechanic.ballistic|mechanic.heavy_penetration_trait"
    rows[0]["反重便利性"] = "待评价"
    rows[0]["玩家评价"] = "玩具"
    item = load_knowledge(edited_table(tmp_path, rows)).items[rows[0]["id"]]
    assert item.role_basis("role.anti_tank") == "community_observation"
    assert "role.anti_tank" in item.reference_roles
    assert "mechanic.ballistic" in item.mechanics
    assert "mechanic.heavy_penetration_trait" in item.mechanics
    assert item.anti_tank_ease == "unknown"
    assert item.community_evaluations == frozenset({"community.toy"})
    assert item.prioritized_roles[0] == "role.anti_tank"


@pytest.mark.parametrize("change", ["duplicate", "missing", "unknown_tag", "wrong_column", "wrong_slot"])
def test_invalid_table_is_rejected_with_a_useful_error(tmp_path, change):
    rows = table_rows()
    if change == "duplicate":
        rows.append(dict(rows[0]))
    elif change == "missing":
        rows.pop()
    elif change == "unknown_tag":
        rows[0]["玩家定位"] = "role.does_not_exist"
    elif change == "wrong_column":
        rows[0]["机制标签"] = "role.anti_tank"
    else:
        rows[0]["背包槽"] = "是"
    with pytest.raises(KnowledgeError):
        load_knowledge(edited_table(tmp_path, rows))


def test_community_claim_cannot_be_supported_only_by_a_wiki_source():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    evidence = copy.deepcopy(evidence)
    wiki = next(source["id"] for source in evidence["sources"] if source["kind"] == "wiki")
    evidence["items"][0]["tags"].append({"id": "role.anti_tank", "basis": "community_observation", "source_ids": [wiki]})
    with pytest.raises(KnowledgeError, match="社区来源"):
        validate_evidence(evidence, json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def test_search_excerpt_cannot_be_claimed_as_full_verification():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    evidence["items"][0]["review"]["status"] = "verified"
    with pytest.raises(KnowledgeError, match="搜索摘要"):
        validate_evidence(evidence, json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize("invalid", [None, [], {"schema_version": 1, "taxonomy": None}])
def test_malformed_json_is_a_recoverable_knowledge_error(tmp_path, invalid):
    evidence_path = tmp_path / "broken.json"
    evidence_path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(KnowledgeError):
        load_knowledge(evidence_path=evidence_path)
