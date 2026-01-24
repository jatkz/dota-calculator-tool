"""Pure calculation functions for attack-based damage calculations"""


def calculate_attack_rate(attack_speed, bat):
    """
    Calculate attacks per second.

    Args:
        attack_speed: Attack speed value (default 100)
        bat: Base attack time (default 1.7)

    Returns:
        Attacks per second
    """
    if bat <= 0:
        return 0
    return attack_speed / (100 * bat)


def calculate_damage_per_hit(base_damage, bonus_damage, flat_modifiers, percentage_modifiers):
    """
    Calculate damage per hit with modifiers.
    Flat modifiers are applied first, then percentage modifiers compound.

    Args:
        base_damage: Base damage value
        bonus_damage: Bonus damage value (green damage)
        flat_modifiers: List of flat modifier values (added to damage)
        percentage_modifiers: List of percentage modifier values (as decimals, e.g., 0.25 for +25%)

    Returns:
        Final damage per hit
    """
    # Start with base + bonus
    damage = base_damage + bonus_damage

    # Apply flat modifiers (additive)
    for flat in flat_modifiers:
        damage += flat

    # Apply percentage modifiers (multiplicative/compound)
    for pct in percentage_modifiers:
        damage *= (1 + pct)

    return damage


def calculate_damage_for_n_hits(damage_per_hit, n_hits):
    """
    Calculate total damage for N hits.

    Args:
        damage_per_hit: Damage dealt per hit
        n_hits: Number of hits

    Returns:
        Total damage for N hits
    """
    return damage_per_hit * n_hits


def calculate_time_for_n_hits(n_hits, attack_rate):
    """
    Calculate time required to deal N hits.

    Args:
        n_hits: Number of hits
        attack_rate: Attacks per second

    Returns:
        Time in seconds for N hits
    """
    if attack_rate <= 0:
        return float('inf')
    return n_hits / attack_rate


def calculate_dps(damage_per_hit, attack_rate):
    """
    Calculate damage per second.

    Args:
        damage_per_hit: Damage dealt per hit
        attack_rate: Attacks per second

    Returns:
        Damage per second
    """
    return damage_per_hit * attack_rate


def calculate_damage_in_time(damage_per_hit, attack_rate, seconds):
    """
    Calculate total damage dealt in a given time period.

    Args:
        damage_per_hit: Damage dealt per hit
        attack_rate: Attacks per second
        seconds: Time period in seconds

    Returns:
        Total damage dealt
    """
    return damage_per_hit * attack_rate * seconds


def calculate_physical_reduction(armor):
    """
    Calculate physical damage reduction from armor.
    Uses Dota 2 formula: reduction = (0.06 * armor) / (1 + 0.06 * abs(armor))

    Args:
        armor: Armor value (can be negative)

    Returns:
        Reduction as a decimal (e.g., 0.15 for 15% reduction)
    """
    return (0.06 * armor) / (1 + 0.06 * abs(armor))


def apply_physical_reduction(damage, armor):
    """
    Apply physical damage reduction from armor.

    Args:
        damage: Raw physical damage
        armor: Target's armor value

    Returns:
        Damage after armor reduction
    """
    reduction = calculate_physical_reduction(armor)
    return damage * (1 - reduction)


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


def calculate_hits_to_kill(hp, damage_per_hit, hp_regen=0, attack_rate=1):
    """
    Calculate number of hits needed to kill a target.
    Accounts for HP regeneration between attacks.

    Args:
        hp: Target's HP
        damage_per_hit: Damage dealt per hit (after reductions)
        hp_regen: HP regenerated per second (default 0)
        attack_rate: Attacks per second (default 1)

    Returns:
        Number of hits to kill (integer, rounded up), or float('inf') if can't kill
    """
    if damage_per_hit <= 0:
        return float('inf')

    if hp_regen <= 0 or attack_rate <= 0:
        # No regen or no attacks - simple division
        import math
        return math.ceil(hp / damage_per_hit)

    # Time between attacks
    attack_interval = 1 / attack_rate

    # Effective damage per hit (accounting for regen between attacks)
    regen_per_attack = hp_regen * attack_interval
    effective_damage = damage_per_hit - regen_per_attack

    if effective_damage <= 0:
        # Can't out-damage the regen
        return float('inf')

    import math
    return math.ceil(hp / effective_damage)


def calculate_time_to_kill(hp, damage_per_hit, attack_rate, hp_regen=0):
    """
    Calculate time to kill a target.

    Args:
        hp: Target's HP
        damage_per_hit: Damage dealt per hit (after reductions)
        attack_rate: Attacks per second
        hp_regen: HP regenerated per second (default 0)

    Returns:
        Time in seconds to kill, or float('inf') if can't kill
    """
    if attack_rate <= 0:
        return float('inf')

    hits = calculate_hits_to_kill(hp, damage_per_hit, hp_regen, attack_rate)
    if hits == float('inf'):
        return float('inf')

    return calculate_time_for_n_hits(hits, attack_rate)
