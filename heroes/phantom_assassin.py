class PhantomAssassin:
    """Minimal hero class for Phantom Assassin.

    Contains only basic stats, talent tiers, and mutually-exclusive facets.
    """

    name = "Phantom Assassin"
    attribute_type = "Agility"
    level = 1
    base_hp = 120
    base_hp_regen = 1
    movespeed = 310
    attack_speed = 110
    bat = 1.7
    base_damage = 36
    base_armor = 1
    base_magic_resist = 25
    evasion = 0
    strength = 19
    agility = 21
    intelligence = 15
    strength_per_level = 2
    agility_per_level = 3.4
    intelligence_per_level = 1.7
    turn_rate = 0.8

    # talents: flat list where each entry has stable id, level and selected flag
    talents = [
        {"id": "stifling_dagger_cd", "level": 10, "selected": False},
        {"id": "phantom_strike_duration", "level": 10, "selected": False},
        {"id": "stifling_dagger_instant_pct", "level": 15, "selected": False},
        {"id": "immaterial_evasion", "level": 15, "selected": False},
        {"id": "phantom_strike_attack_speed", "level": 20, "selected": False},
        {"id": "phantom_strike_cast_range", "level": 20, "selected": False},
        {"id": "stifling_dagger_triple", "level": 25, "selected": False},
        {"id": "coup_de_grace_methodical", "level": 25, "selected": False},
    ]

    # mutually exclusive facet flags
    facets = {"sweet_release": False, "methodical": False}

    @classmethod
    def choose_facet(cls, key):
        """Activate exactly one facet at a time on the class.

        Valid keys are the ones in ``facets``; selecting one clears the other.
        """
        if key not in cls.facets:
            return
        for k in cls.facets:
            cls.facets[k] = False
        cls.facets[key] = True
