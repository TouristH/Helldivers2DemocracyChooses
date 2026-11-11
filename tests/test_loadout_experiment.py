"""Experimental presets use the editable equipment knowledge and keep rerolls valid."""

from dataclasses import replace
import json
from random import Random

import pytest

from loadout_experiment import ExperimentError, generate_experimental_loadout, load_templates, reroll_experimental_slot
from loadout_knowledge import ROOT, load_knowledge


PRESETS = ROOT / "loadout_templates.json"
STRATAGEMS = tuple(f"stratagem_{index}" for index in range(4))


@pytest.fixture(scope="module")
def knowledge():
    return load_knowledge()


@pytest.fixture(scope="module")
def catalog():
    return load_templates(PRESETS)


@pytest.mark.parametrize("faction", ["any", "terminids", "automatons", "illuminate"])
def test_default_draw_uses_advancing_presets_from_the_selected_front(knowledge, catalog, faction):
    template, _ = generate_experimental_loadout(knowledge, catalog, faction, Random(12))
    assert (template.faction, template.mission) == (faction, "advance")


def test_each_exact_preset_draws_eight_distinct_slot_appropriate_items(knowledge, catalog):
    assert len(catalog.templates) == 61
    for preset_id in catalog.templates:
        template, loadout = generate_experimental_loadout(knowledge, catalog, preset_id, Random(42))
        assert template.id == preset_id
        assert set(loadout) == {"primary", "secondary", "grenade", "booster", *STRATAGEMS}
        assert len(set(loadout.values())) == 8
        assert all(knowledge.items[item].slot == key.split("_")[0] for key, item in loadout.items())

        stratagems = [knowledge.items[loadout[key]] for key in STRATAGEMS]
        support = [item for item in stratagems if item.support_weapon]
        temporary = [item for item in support if "mechanic.expendable" in item.mechanics and not item.backpack]
        assert sum(bool(item.backpack) for item in stratagems) <= 1
        assert sum(item.category == "vehicle" for item in stratagems) <= 1
        assert len(support) - len(temporary) <= 1
        assert len(temporary) <= int(preset_id in {"expendable_blitz", "bug_support_rotation", "bot_reinforcement_at"})
        if any("mechanic.requires_one_handed" in item.mechanics for item in stratagems):
            assert any("mechanic.one_handed" in knowledge.items[loadout[key]].mechanics for key in ("primary", "secondary"))


def test_bug_rotation_requires_both_persistent_and_temporary_support(knowledge, catalog):
    _, loadout = generate_experimental_loadout(knowledge, catalog, "bug_support_rotation", Random(10))
    supports = [knowledge.items[value] for value in loadout.values() if knowledge.items[value].support_weapon]
    assert sorted("mechanic.expendable" in item.mechanics for item in supports) == [False, True]


def test_medical_secondary_cannot_be_replaced(knowledge, catalog):
    template, loadout = generate_experimental_loadout(knowledge, catalog, "field_medic", Random(7))
    assert loadout["secondary"] == "secondary.p-11-stim-pistol"
    assert reroll_experimental_slot(knowledge, catalog, template.id, loadout, "secondary", Random(3)) is None


def test_shield_primary_reroll_changes_only_that_slot_and_stays_one_handed(knowledge, catalog):
    template, loadout = generate_experimental_loadout(knowledge, catalog, "bot_shield_alley", Random(15))
    loadout["grenade"] = "grenade.g-123-thermite"  # Keeps the required demolition role in a locked slot.
    original = loadout.copy()
    replacement = reroll_experimental_slot(knowledge, catalog, template.id, loadout, "primary", Random(5))
    assert loadout == original
    assert replacement is not None
    assert replacement != original["primary"]
    assert "mechanic.one_handed" in knowledge.items[replacement].mechanics


def test_stratagem_reroll_cannot_remove_required_shield_or_duplicate_another_slot(knowledge, catalog):
    template, loadout = generate_experimental_loadout(knowledge, catalog, "bot_shield_alley", Random(15))
    shield_slot = next(key for key in STRATAGEMS if "mechanic.requires_one_handed" in knowledge.items[loadout[key]].mechanics)
    replacement = reroll_experimental_slot(knowledge, catalog, template.id, loadout, shield_slot, Random(9))
    assert replacement not in loadout.values()
    assert "mechanic.requires_one_handed" in knowledge.items[replacement].mechanics


def test_reroll_rejects_a_locked_item_from_the_wrong_slot(knowledge, catalog):
    template, loadout = generate_experimental_loadout(knowledge, catalog, "field_medic", Random(7))
    loadout["primary"] = loadout["booster"]
    with pytest.raises(ExperimentError):
        reroll_experimental_slot(knowledge, catalog, template.id, loadout, "secondary")


def test_draw_uses_edited_equipment_tags_and_reports_unsatisfiable_template(knowledge, catalog):
    items = dict(knowledge.items)
    for item in knowledge.items.values():
        if item.slot == "primary" and "mechanic.one_handed" in item.mechanics:
            items[item.id] = replace(item, mechanics=item.mechanics - {"mechanic.one_handed"})
    edited = replace(knowledge, items=items)
    with pytest.raises(ExperimentError, match="单手持盾推进"):
        generate_experimental_loadout(edited, catalog, "shield_advance", Random(1))


def test_loader_rejects_an_unknown_required_selector(tmp_path):
    raw = json.loads(PRESETS.read_text(encoding="utf-8"))
    raw["templates"][0]["requires"].append("missing_selector")
    path = tmp_path / PRESETS.name
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ExperimentError, match="missing_selector"):
        load_templates(path)


@pytest.mark.parametrize("preset_id", ["1", "foo.bar"])
def test_loader_rejects_preset_ids_unusable_in_commands(tmp_path, preset_id):
    raw = json.loads(PRESETS.read_text(encoding="utf-8"))
    raw["templates"][0]["id"] = preset_id
    path = tmp_path / PRESETS.name
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ExperimentError, match="模板 ID 无效"):
        load_templates(path)
