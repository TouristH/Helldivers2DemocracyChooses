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
from loadout_knowledge import KnowledgeError, TABLE_PATH, load_knowledge  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=Path, default=TABLE_PATH, help="待校验 CSV，默认使用插件内的表格")
    parser.add_argument("--item", help="精确装备中文名、英文名或 id")
    args = parser.parse_args()
    try:
        knowledge = load_knowledge(table_path=args.table)
    except KnowledgeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.item:
        item = knowledge.find(args.item)
        if item is None:
            print("没有找到该装备", file=sys.stderr)
            return 1
        print(json.dumps({"id": item.id, "名称": item.name, "分类": item.category, "机制标签": sorted(item.mechanics), "玩家定位": sorted(item.player_roles), "玩家评价": sorted(item.community_evaluations), "资料定位": sorted(item.reference_roles), "反重便利性": item.anti_tank_ease, "支援武器槽": item.support_weapon, "背包槽": item.backpack, "表格已修改": item.user_modified, "研究备注": item.research_notes}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"装备数": len(knowledge.items), "槽位": dict(Counter(item.slot for item in knowledge.items.values())), "社区定位覆盖": sum(bool(item.player_roles) for item in knowledge.items.values()), "反重便利性待评价": sum(item.anti_tank_ease == "unknown" for item in knowledge.items.values()), "表格修改数": sum(item.user_modified for item in knowledge.items.values())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
