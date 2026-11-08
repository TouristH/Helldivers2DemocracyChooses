"""Actual shipped workbook mapping, precedence, saved edits, and CSV export."""
import csv
from copy import copy
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import pytest

import loadout_knowledge as knowledge


NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def tag(name):
    return f"{{{NAMESPACE}}}{name}"


def header_columns(archive, worksheet):
    shared = []
    if "xl/sharedStrings.xml" in archive.namelist():
        strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(node.text or "" for node in item.iter(tag("t"))) for item in strings]

    def value(cell):
        if cell.get("t") == "s":
            return shared[int(cell.find(tag("v")).text)]
        if cell.get("t") == "inlineStr":
            return "".join(node.text or "" for node in cell.iter(tag("t")))
        return cell.findtext(tag("v"), default="")

    header = worksheet.find(f"{tag('sheetData')}/{tag('row')}[@r='1']")
    assert header is not None
    return {value(cell): cell.get("r").rstrip("0123456789") for cell in header.findall(tag("c"))}


def workbook_edit(tmp_path: Path, *, player_tags="玩具", formula=False, swap_columns=False) -> Path:
    target = tmp_path / "edited.xlsx"
    with zipfile.ZipFile(knowledge.WORKBOOK_PATH) as source, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output:
        for member in source.infolist():
            payload = source.read(member.filename)
            if member.filename == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(payload)
                columns = header_columns(source, root)
                row = root.find(f"{tag('sheetData')}/{tag('row')}[@r='2']")
                assert row is not None
                address = f"{columns['玩家标签集']}2"
                cell = row.find(f"{tag('c')}[@r='{address}']")
                if cell is None:
                    cell = ET.SubElement(row, tag("c"), {"r": address})
                cell.clear()
                cell.set("r", address)
                if formula:
                    cell.set("t", "str")
                    ET.SubElement(cell, tag("f")).text = f'"{player_tags}"'
                    ET.SubElement(cell, tag("v")).text = player_tags
                else:
                    cell.set("t", "inlineStr")
                    ET.SubElement(ET.SubElement(cell, tag("is")), tag("t")).text = player_tags
                if swap_columns:
                    first, second = columns["玩家标签集"], columns["英文名"]
                    swapped = {first: second, second: first}
                    for cell in root.iter(tag("c")):
                        address = cell.get("r")
                        column = address.rstrip("0123456789")
                        cell.set("r", swapped.get(column, column) + address[len(column):])
                payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            output.writestr(copy(member), payload)
    return target


def test_shipped_workbook_has_fifteen_fields_mapped_by_header():
    with zipfile.ZipFile(knowledge.WORKBOOK_PATH) as archive:
        worksheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        columns = header_columns(archive, worksheet)
    assert len(columns) == len(knowledge.CSV_FIELDS) == 15
    assert set(columns) == set(knowledge.CSV_FIELDS)
    assert "玩家标签集" in columns
    assert not {"玩家定位", "玩家评价", "反重便利性"} & columns.keys()
    rows = knowledge.read_workbook_rows(knowledge.WORKBOOK_PATH, knowledge.CSV_FIELDS)
    loaded = knowledge.load_knowledge(knowledge.WORKBOOK_PATH)
    assert {row["id"] for row in rows} == set(loaded.items)
    for row in rows:
        assert row["名称"] == loaded.items[row["id"]].name
        assert row["英文名"] == loaded.items[row["id"]].name_en


def test_default_reads_the_workbook_and_explicit_csv_stays_available():
    assert knowledge.load_knowledge().table_path == knowledge.WORKBOOK_PATH
    assert knowledge.load_knowledge(knowledge.TABLE_PATH).table_path == knowledge.TABLE_PATH


def test_csv_is_used_only_if_workbook_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "WORKBOOK_PATH", tmp_path / "absent.xlsx")
    assert knowledge.load_knowledge().table_path == knowledge.TABLE_PATH


def test_invalid_present_workbook_does_not_silently_use_old_csv(tmp_path, monkeypatch):
    broken = tmp_path / "broken.xlsx"
    broken.write_text("invalid workbook", encoding="utf-8")
    monkeypatch.setattr(knowledge, "WORKBOOK_PATH", broken)
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.load_knowledge()


def test_saved_excel_edit_is_seen_on_next_read_and_keeps_research_evidence(tmp_path):
    before = knowledge.EVIDENCE_PATH.read_bytes()
    path = workbook_edit(tmp_path, player_tags="控场；清杂；易误伤")
    first_id = next(iter(knowledge.load_knowledge(path).items))
    item = knowledge.load_knowledge(path).items[first_id]
    assert item.player_tags == frozenset({"player.crowd_control", "player.crowd_clear", "player.friendly_fire_risk"})
    workbook_edit(tmp_path, player_tags="反重；简易使用；对单")
    changed = knowledge.load_knowledge(path).items[first_id]
    assert changed.player_tags == frozenset({"player.anti_tank", "player.easy_to_use", "player.single_target"})
    assert knowledge.EVIDENCE_PATH.read_bytes() == before


def test_excel_column_order_is_resolved_from_headers(tmp_path):
    before = knowledge.load_knowledge(knowledge.WORKBOOK_PATH)
    first_id = next(iter(before.items))
    path = workbook_edit(tmp_path, player_tags="player.crowd_control|清杂；易误伤", swap_columns=True)
    item = knowledge.load_knowledge(path).items[first_id]
    assert item.player_tags == frozenset({"player.crowd_control", "player.crowd_clear", "player.friendly_fire_risk"})
    assert item.name_en == before.items[first_id].name_en
    assert item.mechanics == before.items[first_id].mechanics


def test_excel_formula_cache_is_rejected_by_the_plugin_loader(tmp_path):
    with pytest.raises(knowledge.KnowledgeError, match="公式"):
        knowledge.load_knowledge(workbook_edit(tmp_path, formula=True))


def test_workbook_export_to_csv_preserves_effective_values(tmp_path):
    original = knowledge.load_knowledge(workbook_edit(tmp_path, player_tags="控场；player.crowd_clear|易误伤；控场"))
    destination = knowledge.export_csv(original, tmp_path / "export.csv")
    with destination.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames) == knowledge.CSV_FIELDS
        rows = list(reader)
    first_id = next(iter(original.items))
    assert next(row for row in rows if row["id"] == first_id)["玩家标签集"] == "控场；清杂；易误伤"
    restored = knowledge.load_knowledge(destination)
    assert original.items == restored.items


def test_disputed_is_an_independent_player_tag_and_keeps_other_tags(tmp_path):
    path = workbook_edit(tmp_path, player_tags="反重；简易使用；对单；评价有分歧")
    item = next(iter(knowledge.load_knowledge(path).items.values()))
    assert item.player_tags == frozenset({"player.anti_tank", "player.easy_to_use", "player.single_target", "player.disputed"})
    assert item.tag_basis("player.disputed") == "community_observation"
    assert item.player_tag_display == "反重；简易使用；对单；评价有分歧"
    assert not hasattr(item, "anti_tank_ease")
