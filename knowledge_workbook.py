"""Read the editable knowledge worksheet using only Python's standard library.

Only stored values are read. Target columns must contain literal values rather
than formulas, including cached formula results. No package member is extracted,
and relationships never cause external resources or macros to be executed.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import posixpath
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile
import zlib


class WorkbookError(ValueError):
    """An unreadable worksheet must not masquerade as valid equipment data."""


_CELL_REFERENCE = re.compile(r"\$?([A-Za-z]+)\$?([1-9][0-9]*)\Z")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def _name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _name(child) == name]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in element if _name(child) == name), None)


def _xml(archive: zipfile.ZipFile, member: str) -> ET.Element:
    try:
        return ET.fromstring(archive.read(member))
    except KeyError as exc:
        raise WorkbookError(f"工作簿缺少文件：{member}") from exc
    except ET.ParseError as exc:
        raise WorkbookError(f"工作簿 XML 损坏：{member}（{exc}）") from exc


def _target(base: str, relationship: ET.Element) -> str:
    target = relationship.get("Target", "")
    parsed = urlsplit(target)
    if relationship.get("TargetMode", "").casefold() == "external" or parsed.scheme or parsed.netloc:
        raise WorkbookError("装备标签工作表及共享文本不能引用外部文件")
    if not target or parsed.query or parsed.fragment or "\\" in target:
        raise WorkbookError(f"工作簿文件引用无效：{target}")
    decoded = unquote(parsed.path)
    resolved = posixpath.normpath(decoded.lstrip("/") if decoded.startswith("/") else posixpath.join(posixpath.dirname(base), decoded))
    if resolved in {"", ".", ".."} or resolved.startswith("../"):
        raise WorkbookError(f"工作簿文件引用超出归档范围：{target}")
    return resolved


def _relationships(archive: zipfile.ZipFile, workbook: str) -> dict[str, ET.Element]:
    member = posixpath.join(posixpath.dirname(workbook), "_rels", posixpath.basename(workbook) + ".rels")
    result = {}
    for relationship in _children(_xml(archive, member), "Relationship"):
        key = relationship.get("Id", "")
        if not key or key in result:
            raise WorkbookError("工作簿包含缺失或重复的文件关系 ID")
        result[key] = relationship
    return result


def _workbook_part(archive: zipfile.ZipFile) -> str:
    if "_rels/.rels" in archive.namelist():
        candidates = [rel for rel in _children(_xml(archive, "_rels/.rels"), "Relationship")
                      if rel.get("Type", "").endswith("/officeDocument")]
        if len(candidates) > 1:
            raise WorkbookError("归档中存在多个工作簿入口")
        if candidates:
            return _target("", candidates[0])
    return "xl/workbook.xml"


def _string_value(element: ET.Element | None) -> str:
    """Join visible text runs, excluding phonetic annotations and formatting."""
    if element is None:
        return ""
    parts = []
    for child in element:
        if _name(child) == "t":
            parts.append(child.text or "")
        elif _name(child) == "r":
            parts.extend(text.text or "" for text in _children(child, "t"))
    return "".join(parts)


def _coordinate(reference: str) -> tuple[int, int]:
    match = _CELL_REFERENCE.fullmatch(reference)
    if match is None:
        raise WorkbookError(f"工作表单元格地址无效：{reference}")
    column = 0
    for letter in match[1].upper():
        column = column * 26 + ord(letter) - ord("A") + 1
    return column - 1, int(match[2])


def _row_cells(row: ET.Element, previous_row: int) -> tuple[int, dict[int, ET.Element]]:
    cells = _children(row, "c")
    row_reference = row.get("r")
    if row_reference is None:
        row_number = _coordinate(cells[0].get("r"))[1] if cells and cells[0].get("r") else previous_row + 1
    elif re.fullmatch(r"[1-9][0-9]*", row_reference):
        row_number = int(row_reference)
    else:
        raise WorkbookError(f"工作表行号无效：{row_reference}")
    if row_number <= previous_row:
        raise WorkbookError(f"工作表行号重复或顺序错误：{row_number}")
    result = {}
    next_column = 0
    for cell in cells:
        reference = cell.get("r")
        column, cell_row = _coordinate(reference) if reference else (next_column, row_number)
        if cell_row != row_number or column in result:
            raise WorkbookError(f"工作表第 {row_number} 行含不一致或重复的单元格地址：{reference}")
        result[column] = cell
        next_column = column + 1
    return row_number, result


def _formula_ranges(rows: list[ET.Element]) -> list[tuple[int, int, int, int]]:
    result = []
    for row in rows:
        for cell in _children(row, "c"):
            formula = _child(cell, "f")
            reference = formula.get("ref", "") if formula is not None else ""
            if reference:
                ends = reference.split(":")
                if len(ends) in {1, 2} and all(_CELL_REFERENCE.fullmatch(end) for end in ends):
                    first, last = _coordinate(ends[0]), _coordinate(ends[-1])
                    result.append((min(first[0], last[0]), min(first[1], last[1]), max(first[0], last[0]), max(first[1], last[1])))
    return result


def read_workbook_rows(path: Path, fields: Sequence[str], sheet_name: str = "装备标签") -> list[dict[str, str]]:
    """Read fields by header name; ignore user columns outside the field mapping.

    Shared and inline strings, rich text, empty cells, booleans and raw numeric
    values are supported. Numeric display formats and dates are not converted.
    Every call reopens the saved workbook so edits take effect immediately.
    """
    fields = tuple(fields)
    if not fields or any(not isinstance(field, str) or not field for field in fields) or len(set(fields)) != len(fields):
        raise WorkbookError("目标字段必须为非空且不重复的字段名")
    try:
        with zipfile.ZipFile(path) as archive:
            workbook_part = _workbook_part(archive)
            workbook = _xml(archive, workbook_part)
            sheets = _child(workbook, "sheets")
            matching = [sheet for sheet in _children(sheets, "sheet") if sheet.get("name") == sheet_name] if sheets is not None else []
            if not matching:
                raise WorkbookError(f"工作簿缺少工作表「{sheet_name}」")
            if len(matching) != 1:
                raise WorkbookError(f"工作表名称重复：「{sheet_name}」")
            relation_id = next((value for key, value in matching[0].attrib.items() if key.rsplit("}", 1)[-1] == "id"), None)
            relationships = _relationships(archive, workbook_part)
            relation = relationships.get(relation_id)
            if relation is None or not relation.get("Type", "").endswith("/worksheet"):
                raise WorkbookError(f"工作表「{sheet_name}」的文件关系无效")
            worksheet = _xml(archive, _target(workbook_part, relation))
            sheet_data = _child(worksheet, "sheetData")
            rows = _children(sheet_data, "row") if sheet_data is not None else []
            if not rows:
                raise WorkbookError(f"工作表「{sheet_name}」第一行缺少表头")
            shared_strings: list[str] | None = None

            def shared_value(index: str, address: str) -> str:
                nonlocal shared_strings
                if shared_strings is None:
                    candidates = [rel for rel in relationships.values() if rel.get("Type", "").endswith("/sharedStrings")]
                    if len(candidates) > 1:
                        raise WorkbookError("工作簿包含多个共享文本表")
                    member = _target(workbook_part, candidates[0]) if candidates else posixpath.join(posixpath.dirname(workbook_part), "sharedStrings.xml")
                    shared_strings = [_string_value(item) for item in _children(_xml(archive, member), "si")]
                if not re.fullmatch(r"[0-9]+", index) or int(index) >= len(shared_strings):
                    raise WorkbookError(f"单元格 {address} 的共享文本索引无效：{index}")
                return shared_strings[int(index)]

            def cell_value(cell: ET.Element | None, address: str) -> str:
                if cell is None:
                    return ""
                if _child(cell, "f") is not None:
                    raise WorkbookError(f"单元格 {address} 使用了公式，请粘贴为值后保存；不会读取公式缓存")
                kind = cell.get("t", "n")
                if kind not in {"s", "inlineStr", "str", "b", "n"}:
                    raise WorkbookError(f"单元格 {address} 的类型不受支持：{kind}")
                if kind == "inlineStr":
                    return _string_value(_child(cell, "is"))
                value = _child(cell, "v")
                if value is None or value.text is None:
                    return ""
                text = value.text
                if kind == "str":
                    return text
                text = text.strip()
                if kind == "s":
                    return shared_value(text, address)
                if kind == "b":
                    if text.casefold() not in {"0", "1", "true", "false"}:
                        raise WorkbookError(f"单元格 {address} 的布尔值无效：{text}")
                    return "true" if text.casefold() in {"1", "true"} else "false"
                if not _NUMBER.fullmatch(text):
                    raise WorkbookError(f"单元格 {address} 的数值无效：{text}")
                return text

            header_number, header_cells = _row_cells(rows[0], 0)
            if header_number != 1:
                raise WorkbookError(f"工作表「{sheet_name}」第一行必须为表头")
            column_map = {}
            for column, cell in header_cells.items():
                name = cell_value(cell, cell.get("r", f"第 {column + 1} 列第 1 行")).strip()
                if name in fields:
                    if name in column_map:
                        raise WorkbookError(f"工作表表头重复：{name}")
                    column_map[name] = column
            missing = [field for field in fields if field not in column_map]
            if missing:
                raise WorkbookError("工作表缺少字段：" + "、".join(missing))
            formula_ranges = _formula_ranges(rows)
            result = []
            previous_row = header_number
            for row in rows[1:]:
                row_number, cells = _row_cells(row, previous_row)
                previous_row = row_number
                record = {}
                for field in fields:
                    column = column_map[field]
                    address = f"「{field}」列第 {row_number} 行"
                    if any(left <= column <= right and top <= row_number <= bottom for left, top, right, bottom in formula_ranges):
                        raise WorkbookError(f"单元格 {address} 位于公式区域，请粘贴为值后保存；不会读取公式缓存")
                    record[field] = cell_value(cells.get(column), address)
                if any(value.strip() for value in record.values()):
                    result.append(record)
            return result
    except WorkbookError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, ValueError, NotImplementedError, zlib.error) as exc:
        raise WorkbookError(f"Excel 工作簿读取失败：{exc}") from exc
