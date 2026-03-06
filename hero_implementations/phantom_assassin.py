"""Phantom Assassin hero implementation glue."""

from __future__ import annotations

from heroes.phantom_assassin import PhantomAssassin
from spells.stifling_dagger import STIFLING_DAGGER_STATS, stifling_dagger

from .helpers import build_talents_payload, deep_copy, normalize_key


class PhantomAssassinImplementation:
    """Hero-specific behavior for templates, talents, and spell runtime."""

    _STIFLING_KEY = "stiflingdagger"

    def get_hero_fields_template(self):
        return {
            "name": PhantomAssassin.name,
            "attribute_type": PhantomAssassin.attribute_type,
            "level": str(PhantomAssassin.level),
            "base_hp": str(PhantomAssassin.base_hp),
            "base_hp_regen": str(PhantomAssassin.base_hp_regen),
            "movespeed": str(PhantomAssassin.movespeed),
            "attack_speed": str(PhantomAssassin.attack_speed),
            "bat": str(PhantomAssassin.bat),
            "base_damage": str(PhantomAssassin.base_damage),
            "base_armor": str(PhantomAssassin.base_armor),
            "base_magic_resist": str(PhantomAssassin.base_magic_resist),
            "evasion": str(PhantomAssassin.evasion),
            "strength": str(PhantomAssassin.strength),
            "agility": str(PhantomAssassin.agility),
            "intelligence": str(PhantomAssassin.intelligence),
            "strength_per_level": str(PhantomAssassin.strength_per_level),
            "agility_per_level": str(PhantomAssassin.agility_per_level),
            "intelligence_per_level": str(PhantomAssassin.intelligence_per_level),
            "turn_rate": str(PhantomAssassin.turn_rate),
        }

    def get_spells_template(self):
        cast_animation = STIFLING_DAGGER_STATS.get("cast_animation", 0)
        levels = []
        for idx in range(4):
            factor = STIFLING_DAGGER_STATS["instant_attack_factor"][idx]
            bonus = STIFLING_DAGGER_STATS["attack_damage_bonus"][idx]
            base_damage = PhantomAssassin.base_damage + PhantomAssassin.agility
            levels.append({
                "effects": {
                    "Damage": str(round(base_damage * factor + bonus, 2)),
                    "Damage Type": "Physical",
                    "Hits": "1",
                    "Cast": str(cast_animation),
                    "Mana": str(STIFLING_DAGGER_STATS.get("mana_cost", 30)),
                    "Cooldown": str(STIFLING_DAGGER_STATS.get("cooldown", 6)),
                }
            })
        base_level = deep_copy(levels[0])
        level_overrides = []
        parent = deep_copy(base_level)
        for level in levels[1:]:
            override = {}
            for key, value in level.items():
                if parent.get(key) != value:
                    override[key] = deep_copy(value)
            level_overrides.append(override)
            parent = deep_copy(level)

        metadata = {
            "attack_damage_factor": deep_copy(STIFLING_DAGGER_STATS.get("instant_attack_factor", [])),
            "attack_damage_bonus": deep_copy(STIFLING_DAGGER_STATS.get("attack_damage_bonus", [])),
            "cast_range": deep_copy(STIFLING_DAGGER_STATS.get("cast_range", [])),
            "targets_base": STIFLING_DAGGER_STATS.get("targets", 1),
            "targets_with_talent": 3,
            "move_speed_slow_pct": STIFLING_DAGGER_STATS.get("move_speed_slow_pct", 50),
            "slow_duration": deep_copy(STIFLING_DAGGER_STATS.get("slow_duration", [])),
            "cast_animation": cast_animation,
            "runtime_inputs": {
                "hero_kills_credited_this_cast": 0,
                "target_armors_csv": "0",
            },
        }

        return [{
            "name": "Stifling Dagger",
            "max_level": 4,
            "current_level": 1,
            "base_level": base_level,
            "level_overrides": level_overrides,
            "metadata": metadata,
        }]

    def get_talents_template(self):
        return build_talents_payload({})

    def normalize_talents(self, talents_payload):
        payload = build_talents_payload(talents_payload)
        # Preserve stable ids used by spell helpers.
        id_by_level_side = {
            (10, "left"): "stifling_dagger_cd",
            (10, "right"): "phantom_strike_duration",
            (15, "left"): "stifling_dagger_instant_pct",
            (15, "right"): "immaterial_evasion",
            (20, "left"): "phantom_strike_attack_speed",
            (20, "right"): "phantom_strike_cast_range",
            (25, "left"): "stifling_dagger_triple",
            (25, "right"): "coup_de_grace_methodical",
        }
        for tier in payload.get("tiers", []):
            if not isinstance(tier, dict):
                continue
            level = int(tier.get("level", 0) or 0)
            for side in ("left", "right"):
                node = tier.get(side, {})
                if isinstance(node, dict):
                    node["id"] = id_by_level_side.get((level, side), node.get("id") or f"level_{level}_{side}")
        return payload

    def resolve_talent_effects(self, payload):
        talents = self.normalize_talents((payload or {}).get("talents", {}))
        effects = []

        def add(effect_id, tier_level, side, label, target, field, operation, value, simulated, note=""):
            effects.append({
                "id": effect_id,
                "tier_level": tier_level,
                "side": side,
                "label": label,
                "target": target,
                "field": field,
                "operation": operation,
                "value": value,
                "simulated": bool(simulated),
                "note": note,
            })

        for tier in talents.get("tiers", []):
            if not isinstance(tier, dict):
                continue
            level = int(tier.get("level", 0) or 0)
            side = tier.get("selected_side")
            if side not in ("left", "right"):
                continue
            node = tier.get(side, {})
            talent_id = str(node.get("id", ""))
            label = str(node.get("label", talent_id))

            if talent_id == "immaterial_evasion":
                add(talent_id, level, side, label, "hero", "evasion_pct", "add", 20, True)
            elif talent_id == "phantom_strike_attack_speed":
                add(talent_id, level, side, label, "hero", "attack_speed", "add", 60, True)
            else:
                # Non-simulated effects are still surfaced in UI/runtime text.
                add(talent_id, level, side, label, "spell", "metadata", "note", 0, False)

        return effects

    def normalize_spell_metadata(self, spell_name, metadata):
        data = deep_copy(metadata) if isinstance(metadata, dict) else {}
        runtime_inputs = data.get("runtime_inputs", {})
        if not isinstance(runtime_inputs, dict):
            runtime_inputs = {}
        runtime_inputs.setdefault("hero_kills_credited_this_cast", 0)
        runtime_inputs.setdefault("target_armors_csv", "0")
        data["runtime_inputs"] = runtime_inputs

        if normalize_key(spell_name) == self._STIFLING_KEY:
            data.setdefault("attack_damage_factor", deep_copy(STIFLING_DAGGER_STATS.get("instant_attack_factor", [])))
            data.setdefault("attack_damage_bonus", deep_copy(STIFLING_DAGGER_STATS.get("attack_damage_bonus", [])))
            data.setdefault("cast_range", deep_copy(STIFLING_DAGGER_STATS.get("cast_range", [])))
            data.setdefault("slow_duration", deep_copy(STIFLING_DAGGER_STATS.get("slow_duration", [])))
            data.setdefault("move_speed_slow_pct", STIFLING_DAGGER_STATS.get("move_speed_slow_pct", 50))
            data.setdefault("cast_animation", STIFLING_DAGGER_STATS.get("cast_animation", 0.3))
            data.setdefault("targets_base", 1)
            data.setdefault("targets_with_talent", 3)
            data.setdefault("scepter_shard_cooldown_on_hero_kill", 4)

        return data

    def _selected_talent_list(self, talents_payload):
        """Return a flat selected-talent list for spell helper compatibility."""
        talents = self.normalize_talents(talents_payload)
        selected = []
        for tier in talents.get("tiers", []):
            if not isinstance(tier, dict):
                continue
            side = tier.get("selected_side")
            if side not in ("left", "right"):
                continue
            node = tier.get(side, {})
            if not isinstance(node, dict):
                continue
            selected.append({
                "id": node.get("id"),
                "level": tier.get("level"),
                "label": node.get("label"),
                "selected": True,
            })
        return selected

    def evaluate_spell(self, spell_state, hero_state, eval_context):
        spell_name = normalize_key((spell_state or {}).get("spell_name", ""))
        if spell_name != self._STIFLING_KEY:
            return {}

        level_index = int((spell_state or {}).get("level_index", 0) or 0)
        runtime_inputs = (spell_state or {}).get("runtime_inputs", {})
        if not isinstance(runtime_inputs, dict):
            runtime_inputs = {}
        hero_kills = int(runtime_inputs.get("hero_kills_credited_this_cast", 0) or 0)

        selected_targets = (eval_context or {}).get("selected_targets", [])
        if not isinstance(selected_targets, list) or not selected_targets:
            selected_targets = [{"name": "Target 1", "armor": 0.0}]

        caster = {
            "hero_name": (hero_state or {}).get("hero_name", "Phantom Assassin"),
            "attack_damage": float((hero_state or {}).get("hero_auto_attack_damage", 0) or 0),
            "talents": [],
            "facets": (hero_state or {}).get("facets") or {},
        }

        # Convert incoming effects into selected talent ids for spell helper flags.
        effects = (hero_state or {}).get("talent_effects", [])
        selected_ids = set()
        for effect in effects if isinstance(effects, list) else []:
            if isinstance(effect, dict) and effect.get("id"):
                selected_ids.add(str(effect["id"]))
        if selected_ids:
            caster["talents"] = [{"id": sid, "selected": True} for sid in sorted(selected_ids)]

        per_target = []
        for target in selected_targets:
            armor = float((target or {}).get("armor", 0) or 0)
            result = stifling_dagger(caster, level_index=level_index, target={"armor": armor})
            per_target.append({
                "name": (target or {}).get("name", "Target"),
                "armor": armor,
                "raw": float(result.get("raw", 0) or 0),
                "after_reduction": float(result.get("after_reduction", 0) or 0),
                "cooldown": float(result.get("cooldown", 0) or 0),
                "targets": int(result.get("targets", 1) or 1),
            })

        if not per_target:
            return {}

        first = per_target[0]
        cooldown_after_shard = max(0.0, first["cooldown"] - (4.0 * max(0, hero_kills)))

        return {
            "spell_key": spell_name,
            "per_target": per_target,
            "raw": first["raw"],
            "after_reduction": first["after_reduction"],
            "cooldown": first["cooldown"],
            "cooldown_after_shard": cooldown_after_shard,
            "target_count": first["targets"],
        }

    def build_spell_runtime_ui_model(self, spell_state, result):
        if normalize_key((spell_state or {}).get("spell_name", "")) != self._STIFLING_KEY:
            return {"talent_text": "", "runtime_status": ""}

        if not isinstance(result, dict) or not result:
            return {"talent_text": "", "runtime_status": ""}

        count = int(result.get("target_count", 1) or 1)
        per_target = result.get("per_target", [])
        damage_parts = []
        for row in per_target[:4]:
            if isinstance(row, dict):
                damage_parts.append(f"{row.get('name', 'Target')}: {float(row.get('after_reduction', 0)):.2f}")

        talent_text = ""
        if count >= 3:
            talent_text = "Triple Stifling Dagger active"

        runtime_status = (
            f"CD {float(result.get('cooldown_after_shard', 0)):.2f}s"
            + (f" | {'; '.join(damage_parts)}" if damage_parts else "")
        )
        return {
            "talent_text": talent_text,
            "runtime_status": runtime_status,
        }
