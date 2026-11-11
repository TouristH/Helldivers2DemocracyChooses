#!/usr/bin/env python3
"""Validate the same editable table used by the plugin; optionally inspect an item."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from loadout_knowledge import KnowledgeError, export_csv, load_knowledge  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=Path, help="待校验 XLSX/CSV，默认优先使用插件目录内的 XLSX")
    parser.add_argument("--item", help="精确装备中文名、英文名或 id")
    parser.add_argument("--export-csv", type=Path, help="将当前实际读取的表格导出为标准 UTF-8 CSV")
    args = parser.parse_args()
    try:
        knowledge = load_knowledge(table_path=args.table)
        if args.export_csv is not None:
            export_csv(knowledge, args.export_csv)
    except (KnowledgeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.item:
        item = knowledge.find(args.item)
        if item is None:
            print("没有找到该装备", file=sys.stderr)
            return 1
        print(json.dumps({"id": item.id, "名称": item.name, "分类": item.category, "机制标签": sorted(item.mechanics), "玩家标签": sorted(item.player_tags), "玩家标签集（仅显示）": item.player_tag_display, "资料定位": sorted(item.reference_roles), "支援武器槽": item.support_weapon, "背包槽": item.backpack, "表格已修改": item.user_modified, "研究备注": item.research_notes}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"读取文件": str(knowledge.table_path), "装备数": len(knowledge.items), "槽位": dict(Counter(item.slot for item in knowledge.items.values())), "玩家标签覆盖": knowledge.player_tag_count, "玩家词表标签数": len(knowledge.taxonomy["player_tag_order"]), "表格修改数": sum(item.user_modified for item in knowledge.items.values())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
