"""Interoperable XLSX values, column mapping and formula-cache rejection."""
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile
import struct

import pytest

from knowledge_workbook import WorkbookError, read_workbook_rows


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def test_broken_compressed_member_is_reported_as_a_workbook_error(tmp_path):
    path = workbook(tmp_path, f'<row r="1">{inline("A1", "id")}</row>')
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("xl/workbook.xml")
    payload = bytearray(path.read_bytes())
    filename_length, extra_length = struct.unpack_from("<HH", payload, info.header_offset + 26)
    start = info.header_offset + 30 + filename_length + extra_length
    payload[start] |= 0x06  # DEFLATE reserved block type, rather than a valid cell value.
    path.write_bytes(payload)
    with pytest.raises(WorkbookError, match="读取失败"):
        read_workbook_rows(path, ("id",))


def inline(address: str, value: str) -> str:
    return f'<c r="{address}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'


def workbook(tmp_path: Path, rows: str, *, sheet_name="装备标签", shared_strings=None,
             target="worksheets/tags.xml", external=False, main_namespace=MAIN) -> Path:
    path = tmp_path / "knowledge.xlsx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{main_namespace}" xmlns:r="{REL}"><sheets><sheet name="字典" sheetId="1" r:id="rOther"/><sheet name="{sheet_name}" sheetId="2" r:id="rTags"/></sheets></workbook>')
        shared_relation = f'<Relationship Id="rStrings" Type="{REL}/sharedStrings" Target="sharedStrings.xml"/>' if shared_strings is not None else ""
        mode = ' TargetMode="External"' if external else ""
        archive.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{PACKAGE_REL}"><Relationship Id="rOther" Type="{REL}/worksheet" Target="worksheets/dictionary.xml"/><Relationship Id="rTags" Type="{REL}/worksheet" Target="{target}"{mode}/>{shared_relation}</Relationships>')
        archive.writestr("xl/worksheets/dictionary.xml", f'<worksheet xmlns="{MAIN}"><sheetData><row r="1">{inline("A1", "不应读取这张表")}</row></sheetData></worksheet>')
        archive.writestr("xl/worksheets/tags.xml", f'<worksheet xmlns="{main_namespace}"><sheetData>{rows}</sheetData></worksheet>')
        if shared_strings is not None:
            archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="{main_namespace}">{shared_strings}</sst>')
    return path


def test_reordered_headers_map_by_name_and_ignore_extra_user_columns(tmp_path):
    rows = (f'<row r="1">{inline("A1", "用户计算")}{inline("B1", "名称")}{inline("D1", "id")}</row>'
            f'<row r="2"><c r="A2"><f>1+1</f><v>2</v></c>{inline("B2", "样本武器")}{inline("D2", "primary.sample")}</row>')
    result = read_workbook_rows(workbook(tmp_path, rows), ("id", "名称"))
    assert result == [{"id": "primary.sample", "名称": "样本武器"}]
    assert list(result[0]) == ["id", "名称"]


def test_shared_strings_rich_runs_sparse_columns_and_absent_values(tmp_path):
    strings = '<si><t>id</t></si><si><r><t>名</t></r><r><rPr><b/></rPr><t>称</t></r><rPh sb="0" eb="2"><t>ignored pronunciation</t></rPh></si><si><r><t>主</t></r><r><t>武器</t></r></si>'
    rows = ('<row r="1"><c r="B1" t="s"><v>0</v></c><c r="AA1" t="s"><v>1</v></c>' + inline("AC1", "备注") + '</row>'
            '<row r="3">' + inline("B3", "primary.sample") + '<c r="AA3" t="s"><v>2</v></c><c r="AC3" s="2"/></row>'
            '<row r="4"><c r="B4" s="1"/><c r="AA4" t="inlineStr"><is><t/></is></c></row>')
    assert read_workbook_rows(workbook(tmp_path, rows, shared_strings=strings), ("id", "名称", "备注")) == [{"id": "primary.sample", "名称": "主武器", "备注": ""}]


def test_inline_rich_text_preserves_visible_spacing_and_ignores_phonetic_text(tmp_path):
    rows = '<row>' + inline("A1", "id") + '</row><row><c t="inlineStr"><is><r><t xml:space="preserve"> x </t></r><r><t>&amp;y</t></r><rPh><t>phonetic</t></rPh></is></c></row>'
    assert read_workbook_rows(workbook(tmp_path, rows), ("id",)) == [{"id": " x &y"}]


def test_boolean_numbers_and_literal_string_values(tmp_path):
    rows = ('<row r="1">' + inline("A1", "id") + inline("B1", "背包槽") + inline("C1", "数字") + inline("D1", "文字") + '</row>'
            '<row r="2">' + inline("A2", "one") + '<c r="B2" t="b"><v>1</v></c><c r="C2"><v>1.25e+2</v></c><c r="D2" t="str"><v>literal</v></c></row>'
            '<row r="3">' + inline("A3", "two") + '<c r="B3" t="b"><v>0</v></c><c r="C3" t="n"><v>0</v></c></row>')
    assert read_workbook_rows(workbook(tmp_path, rows), ("id", "背包槽", "数字", "文字")) == [
        {"id": "one", "背包槽": "true", "数字": "1.25e+2", "文字": "literal"},
        {"id": "two", "背包槽": "false", "数字": "0", "文字": ""},
    ]


@pytest.mark.parametrize("formula", ['<f>"cached"</f>', '<f t="shared" si="0"/>', '<f t="array" ref="A2:A3">SOMEFUNCTION()</f>'])
def test_formula_in_target_column_is_rejected_instead_of_reading_cache(tmp_path, formula):
    rows = f'<row r="1">{inline("A1", "id")}</row><row r="2"><c r="A2" t="str">{formula}<v>cached</v></c></row>'
    with pytest.raises(WorkbookError, match="公式"):
        read_workbook_rows(workbook(tmp_path, rows), ("id",))


def test_formula_range_covering_target_column_rejects_cached_spill_cells(tmp_path):
    rows = (f'<row r="1">{inline("A1", "用户计算")}{inline("B1", "id")}</row>'
            '<row r="2"><c r="A2" t="str"><f t="array" ref="A2:B2">SOMEFUNCTION()</f><v>x</v></c><c r="B2" t="str"><v>stale-cache</v></c></row>')
    with pytest.raises(WorkbookError, match="公式区域"):
        read_workbook_rows(workbook(tmp_path, rows), ("id",))


def test_missing_required_field_is_reported(tmp_path):
    rows = f'<row r="1">{inline("A1", "id")}</row>'
    with pytest.raises(WorkbookError, match="缺少字段.*名称"):
        read_workbook_rows(workbook(tmp_path, rows), ("id", "名称"))


def test_duplicate_target_header_is_rejected(tmp_path):
    rows = f'<row r="1">{inline("A1", " id ")}{inline("B1", "id")}</row>'
    with pytest.raises(WorkbookError, match="表头重复.*id"):
        read_workbook_rows(workbook(tmp_path, rows), ("id",))


def test_missing_sheet_does_not_read_dictionary_sheet(tmp_path):
    rows = f'<row r="1">{inline("A1", "id")}</row>'
    with pytest.raises(WorkbookError, match="缺少工作表.*装备标签"):
        read_workbook_rows(workbook(tmp_path, rows, sheet_name="其他"), ("id",))


@pytest.mark.parametrize("kind,value", [("e", "#REF!"), ("d", "2026-11-08"), ("unsupported", "x")])
def test_unsupported_mapped_cell_type_is_rejected(tmp_path, kind, value):
    rows = f'<row r="1">{inline("A1", "id")}</row><row r="2"><c r="A2" t="{kind}"><v>{value}</v></c></row>'
    with pytest.raises(WorkbookError, match="类型不受支持"):
        read_workbook_rows(workbook(tmp_path, rows), ("id",))


def test_unsupported_values_in_extra_columns_are_ignored(tmp_path):
    rows = (f'<row r="1">{inline("A1", "用户错误")}{inline("B1", "id")}</row>'
            f'<row r="2"><c r="A2" t="e"><v>#VALUE!</v></c>{inline("B2", "valid")}</row>')
    assert read_workbook_rows(workbook(tmp_path, rows), ("id",)) == [{"id": "valid"}]


@pytest.mark.parametrize("target", ["/xl/worksheets/tags.xml", "worksheets/../worksheets/tags.xml"])
def test_absolute_and_relative_package_relationships_are_supported(tmp_path, target):
    rows = f'<row r="1">{inline("A1", "id")}</row><row r="2">{inline("A2", "valid")}</row>'
    assert read_workbook_rows(workbook(tmp_path, rows, target=target), ("id",)) == [{"id": "valid"}]


def test_strict_spreadsheet_namespace_is_read(tmp_path):
    rows = f'<row r="1">{inline("A1", "id")}</row><row r="2">{inline("A2", "valid")}</row>'
    assert read_workbook_rows(workbook(tmp_path, rows, main_namespace="http://purl.oclc.org/ooxml/spreadsheetml/main"), ("id",)) == [{"id": "valid"}]


def test_external_sheet_relationship_is_rejected_without_networking(tmp_path):
    with pytest.raises(WorkbookError, match="不能引用外部文件"):
        read_workbook_rows(workbook(tmp_path, '', target="https://example.invalid/sheet.xml", external=True), ("id",))


@pytest.mark.parametrize("value", ["99", "-1", "bad"])
def test_invalid_shared_string_index_is_a_workbook_error(tmp_path, value):
    rows = f'<row r="1">{inline("A1", "id")}</row><row r="2"><c r="A2" t="s"><v>{value}</v></c></row>'
    with pytest.raises(WorkbookError, match="共享文本索引无效"):
        read_workbook_rows(workbook(tmp_path, rows, shared_strings='<si><t>only</t></si>'), ("id",))


def test_saved_changes_are_reread_on_each_call(tmp_path):
    fields = ("id",)
    path = workbook(tmp_path, f'<row r="1">{inline("A1", "id")}</row><row r="2">{inline("A2", "before")}</row>')
    assert read_workbook_rows(path, fields) == [{"id": "before"}]
    workbook(tmp_path, f'<row r="1">{inline("A1", "id")}</row><row r="2">{inline("A2", "after")}</row>')
    assert read_workbook_rows(path, fields) == [{"id": "after"}]


def test_non_zip_file_is_a_clear_workbook_error(tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b'not an xlsx archive')
    with pytest.raises(WorkbookError, match="工作簿读取失败"):
        read_workbook_rows(path, ("id",))
