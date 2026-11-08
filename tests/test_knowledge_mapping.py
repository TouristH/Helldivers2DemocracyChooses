"""Actual shipped workbook mapping, precedence, saved edits, and CSV export."""
import csv
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import pytest

import loadout_knowledge as knowledge


def workbook_edit(tmp_path: Path, *, formula=False) -> Path:
    target = tmp_path / "edited.xlsx"
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    tag = lambda name: f"{{{namespace}}}{name}"
    with zipfile.ZipFile(knowledge.WORKBOOK_PATH) as source, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output:
        for member in source.infolist():
            payload = source.read(member.filename)
            if member.filename == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(payload)
                row = root.find(f"{tag('sheetData')}/{tag('row')}[@r='2']")
                cell = row.find(f"{tag('c')}[@r='D2']")
                if cell is None:
                    cell = ET.SubElement(row, tag("c"), {"r": "D2"})
                cell.clear()
                cell.set("r", "D2")
                if formula:
                    cell.set("t", "str")
                    ET.SubElement(cell, tag("f")).text = '"玩具"'
                    ET.SubElement(cell, tag("v")).text = "玩具"
                else:
                    cell.set("t", "inlineStr")
                    ET.SubElement(ET.SubElement(cell, tag("is")), tag("t")).text = "玩具"
                payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            output.writestr(member, payload)
    return target


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
    path = workbook_edit(tmp_path)
    first_id = next(iter(knowledge.load_knowledge(path).items))
    item = knowledge.load_knowledge(path).items[first_id]
    assert "community.toy" in item.community_evaluations
    assert item.user_modified
    assert knowledge.EVIDENCE_PATH.read_bytes() == before


def test_excel_formula_cache_is_rejected_by_the_plugin_loader(tmp_path):
    with pytest.raises(knowledge.KnowledgeError, match="公式"):
        knowledge.load_knowledge(workbook_edit(tmp_path, formula=True))


def test_workbook_export_to_csv_preserves_effective_values(tmp_path):
    original = knowledge.load_knowledge(workbook_edit(tmp_path))
    destination = knowledge.export_csv(original, tmp_path / "export.csv")
    with destination.open(encoding="utf-8-sig", newline="") as stream:
        assert tuple(csv.DictReader(stream).fieldnames) == knowledge.CSV_FIELDS
    restored = knowledge.load_knowledge(destination)
    assert original.items == restored.items


def test_disagreeing_community_ratings_are_not_silently_marked_unrated():
    entry = dict(next(iter(knowledge.load_knowledge().research.values())))
    entry["community_assessments"] = [{"value": "convenient"}, {"value": "conditional"}]
    assert knowledge._baseline(entry)[6] == "disputed"
