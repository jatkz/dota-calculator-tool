"""Pure calculation functions for spell-based damage calculations"""


def calculate_spell_damage(base_damage, instances, flat_modifiers=None, percentage_modifiers=None):
    """
    Calculate total spell damage with modifiers.

    Args:
        base_damage: Base damage per instance
        instances: Number of damage instances
        flat_modifiers: List of flat modifier values (added to damage)
        percentage_modifiers: List of percentage modifier values (as decimals, e.g., 0.25 for +25%)

    Returns:
        Total spell damage
    """
    flat_modifiers = flat_modifiers or []
    percentage_modifiers = percentage_modifiers or []

    # Start with base damage
    damage = base_damage

    # Apply flat modifiers (additive)
    for flat in flat_modifiers:
        damage += flat

    # Apply percentage modifiers (multiplicative/compound)
    for pct in percentage_modifiers:
        damage *= (1 + pct)

    # Multiply by instances
    return damage * instances


def apply_magic_resistance(damage, magic_resistance):
    """
    Apply magic damage reduction from magic resistance.

    Args:
        damage: Raw magic damage
        magic_resistance: Magic resistance as decimal (e.g., 0.25 for 25%)

    Returns:
        Damage after magic resistance
    """
    return damage * (1 - magic_resistance)


def apply_physical_resistance(damage, armor):
    """
    Apply physical damage reduction from armor.
    Uses Dota 2 formula: reduction = (0.06 * armor) / (1 + 0.06 * abs(armor))

    Args:
        damage: Raw physical damage
        armor: Target's armor value

    Returns:
        Damage after armor reduction
    """
    reduction = (0.06 * armor) / (1 + 0.06 * abs(armor))
    return damage * (1 - reduction)


def calculate_spell_dps(damage, cast_time, cooldown):
    """
    Calculate spell DPS over cooldown cycle.
    DPS = damage / max(cast_time, cooldown)

    Args:
        damage: Total spell damage (after reductions)
        cast_time: Cast animation time
        cooldown: Spell cooldown

    Returns:
        Damage per second over full cooldown cycle
    """
    cycle_time = max(cast_time, cooldown)
    if cycle_time <= 0:
        return 0
    return damage / cycle_time


def calculate_mana_efficiency(damage, mana_cost):
    """
    Calculate damage per mana spent.

    Args:
        damage: Total spell damage (after reductions)
        mana_cost: Mana cost of spell

    Returns:
        Damage per mana point
    """
    if mana_cost <= 0:
        return float('inf') if damage > 0 else 0
    return damage / mana_cost


def calculate_burst_damage(spells_data, target_magic_res=0, target_armor=0):
    """
    Calculate total burst damage from multiple spells.

    Args:
        spells_data: List of dicts with 'damage', 'damage_type' keys
        target_magic_res: Target's magic resistance as decimal
        target_armor: Target's armor value

    Returns:
        Total burst damage after reductions
    """
    total = 0
    for spell in spells_data:
        damage = spell.get('damage', 0)
        damage_type = spell.get('damage_type', 'Magic')

        if damage_type == 'Magic':
            total += apply_magic_resistance(damage, target_magic_res)
        elif damage_type == 'Physical':
            total += apply_physical_resistance(damage, target_armor)
        else:  # Pure
            total += damage

    return total
