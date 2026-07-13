"""
Load weapon and enemy data from MySQL for use in the calculator.
"""
import re

from engine.db import get_connection


def _query(sql, params=None):
    """Execute a read query and return all rows as dicts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def _coalesce(v, default):
    """Producer-side normalisation: NULL DB values become the canonical
    'absent' value (0 / 0.0 / ''). Per parent README NO GUARD RULE,
    consumers access the field directly with no `.get(k, default)`.
    Keep the conversion in ONE place (this loader). When the upstream
    DB column gains NOT NULL, this helper goes away."""
    return default if v is None else v


def _skill_dict(r, is_mastery=False):
    """Build a calculator skill dict from a DB row.

    Every field is always emitted (no None passed through). Downstream
    consumers (routes.py, simulator.py) read fields with direct access.
    """
    name = r['name']
    if is_mastery:
        name += ' (Mastery)'
    return {
        'id': r['internal_id'],
        'name': name,
        'slug': r['unique_slug'],
        'ap_cost': _coalesce(r['action_cost'], 0),
        'stamina_cost': _coalesce(r['fatigue_base_cost'], 0),
        'piercing_perc': _coalesce(r['piercing_perc_bonus'], 0) / 100.0,
        'bonus_damage': _coalesce(r['damage_bonus'], 0),
        'damage_mult': _coalesce(r['damage_perc'], 100) / 100.0,
        'headshot_bonus': 0.0,
        'label': _coalesce(r['label'], ''),
        'damage_calculator_tooltip': _coalesce(r['damage_calculator_tooltip'], ''),
        'headshot_chance_bonus': _coalesce(r['headshot_chance_bonus'], 0),
        'hit_chance_bonus': _coalesce(r['hit_chance_bonus'], 0),
        'bleed_per_turn': _coalesce(r['bleed_per_turn'], 0),
        # weapon_skills DB has no hitpoint_damage_minimum column today;
        # emit 0 so consumers can use direct access. Demolish Armor's
        # 10 HP floor is wired through SKILL_CALC_PARAMS in routes.py.
        'hitpoint_damage_minimum': 0,
        'scales_with_missing_hp': False,
        'is_mastery': is_mastery,
    }


def load_weapons():
    """Load weapons from MySQL with base and mastery skills attached."""
    weapons_rows = _query('SELECT * FROM weapon ORDER BY name')

    skills_rows = _query("""
        SELECT ws.*, m.weapon_id as weapon_name, m.sort_order
        FROM weapon_skill_map m
        JOIN weapon_skill ws ON ws.internal_id = m.internal_id AND ws.is_mastery = 0
        ORDER BY m.weapon_id, m.sort_order
    """)

    mastery_rows = _query("""
        SELECT * FROM weapon_skill
        WHERE is_mastery = 1 AND show_in_calculator = 1
    """)

    mastery_by_name = {}
    for r in mastery_rows:
        mastery_by_name[r['name']] = _skill_dict(r, is_mastery=True)

    # Group skills by weapon, inserting mastery right after each base skill
    weapon_skills = {}
    for r in skills_rows:
        wname = r['weapon_name']
        if wname not in weapon_skills:
            weapon_skills[wname] = []
        weapon_skills[wname].append(_skill_dict(r))
        mastery = mastery_by_name.get(r['name'])
        if mastery:
            weapon_skills[wname].append(dict(mastery))

    weapons = []
    for r in weapons_rows:
        weapons.append({
            'id': r['id'],
            'name': r['name'],
            'two_handed': bool(r['is_two_handed']),
            'damage_min': r['damage_min'],
            'damage_max': r['damage_max'],
            'piercing_perc': r['piercing_perc'] / 100.0,
            'damage_armor_perc': r['armor_damage_perc'] / 100.0,
            'shield_damage': r['shield_damage'],
            'headshot_chance': r['headshot_chance_bonus'],
            'mastery': r['mastery'],
            # Producer-side normalisation: '' for unfactioned weapons
            # so consumers (tag_weapon_names) read with direct access.
            'subfaction': _coalesce(r['subfaction'], ''),
            'slug': r['unique_slug'],
            'fatigue_per_use': r['fatigue_per_use'],
            # weapon_skill_map may be missing rows for a weapon during
            # data-extraction work; consumer raises if so.
            'skills': weapon_skills.get(r['name'], []),
        })
    return weapons


def load_enemies():
    """Load enemies from MySQL."""
    rows = _query('SELECT * FROM enemy ORDER BY name')
    enemies = []
    for r in rows:
        enemies.append({
            'id': r['id'],
            'name': r['name'],
            'racial_origin': r['racial_origin'],
            'hitpoints': r['hitpoints'],
            'body_armor': r['body_armor'],
            'head_armor': r['head_armor'],
            'is_bleed_immune': bool(r['is_bleed_immune']),
            'is_injury_immune': bool(r['is_injury_immune']),
            'is_morale_immune': bool(r['is_morale_immune']),
            'racial_trait': _coalesce(r['racial_trait'], ''),
            'armor_damage_received_perc': r['armor_damage_received_perc'],
            'heal_per_turn': r['heal_per_turn'],
            'slug': r['unique_slug'],
        })
    return enemies


def load_skills():
    """Load weapon skills from MySQL. Returns dict keyed by skill name."""
    rows = _query('SELECT * FROM weapon_skill WHERE is_mastery = 0 ORDER BY name')
    skills = {}
    for r in rows:
        # Non-attack skills (Riposte, Spearwall) have range 0,0 and damage_perc 100
        # with custom_logic. They had piercing = '--' in old files = None.
        # Attack skills get piercing_perc_bonus as a float (0.0 for no bonus).
        is_non_attack = (r['range_min'] == 0 and r['range_max'] == 0)
        skills[r['name']] = {
            'id': r['internal_id'],
            'name': r['name'],
            'ap_cost': r['action_cost'],
            'stamina_cost': r['fatigue_base_cost'],
            'piercing_perc': None if is_non_attack else r['piercing_perc_bonus'] / 100.0,
            'bonus_damage': r['damage_bonus'],
            'damage_mult': r['damage_perc'] / 100.0,
            'headshot_bonus': 0.0,
            'label': _coalesce(r['label'], ''),
            'damage_calculator_tooltip': _coalesce(r['damage_calculator_tooltip'], ''),
            'has_custom_logic': bool(r['has_custom_logic']),
            'custom_logic': _coalesce(r['custom_logic'], ''),
            'headshot_chance_bonus': r['headshot_chance_bonus'],
            'hit_chance_bonus': r['hit_chance_bonus'],
            'bleed_per_turn': r['bleed_per_turn'],
        }
    return skills


def load_mastery_skills():
    """Load mastery variants from MySQL. Returns dict keyed by base skill name."""
    rows = _query('SELECT * FROM weapon_skill WHERE is_mastery = 1 ORDER BY name')
    mastery = {}
    for r in rows:
        is_non_attack = (r['range_min'] == 0 and r['range_max'] == 0)
        mastery[r['name']] = {
            'id': r['internal_id'],
            'name': r['name'],
            'ap_cost': r['action_cost'],
            'stamina_cost': r['fatigue_base_cost'],
            'piercing_perc': None if is_non_attack else r['piercing_perc_bonus'] / 100.0,
            'bonus_damage': r['damage_bonus'],
            'damage_mult': r['damage_perc'] / 100.0,
            'headshot_bonus': 0.0,
            'label': _coalesce(r['label'], ''),
            'damage_calculator_tooltip': _coalesce(r['damage_calculator_tooltip'], ''),
            'has_custom_logic': bool(r['has_custom_logic']),
            'custom_logic': _coalesce(r['custom_logic'], ''),
            'headshot_chance_bonus': r['headshot_chance_bonus'],
            'hit_chance_bonus': r['hit_chance_bonus'],
            'bleed_per_turn': r['bleed_per_turn'],
        }
    return mastery


def load_weapon_to_skills():
    """Load weapon name -> skill name list mapping from MySQL."""
    rows = _query("""
        SELECT m.weapon_id as weapon_name, s.name as skill_name, m.sort_order
        FROM weapon_skill_map m
        JOIN weapon_skill s ON s.internal_id = m.internal_id AND s.is_mastery = 0
        ORDER BY m.weapon_id, m.sort_order
    """)
    mapping = {}
    for r in rows:
        wname = r['weapon_name']
        if wname not in mapping:
            mapping[wname] = []
        mapping[wname].append(r['skill_name'])
    return mapping


# Cache on import
WEAPONS = load_weapons()
ENEMIES = load_enemies()
SKILLS = load_skills()
MASTERY_SKILLS = load_mastery_skills()
WEAPON_TO_SKILLS = load_weapon_to_skills()


def load_armor_loadouts():
    """Load enemy_armor_loadouts into {enemy_id: {body: [...], helmet: [...]}}."""
    rows = _query('SELECT * FROM enemy_armor_loadout ORDER BY enemy_id')
    loadouts = {}
    for r in rows:
        eid = r['enemy_id']
        if eid not in loadouts:
            loadouts[eid] = {'body': [], 'helmet': []}
        loadouts[eid][r['slot']].append({'durability': r['durability'], 'percent': r['percent']})
    return loadouts


ARMOR_LOADOUTS = load_armor_loadouts()


def load_enemy_perks():
    """Load enemy_perks into {enemy_id: [perk_name, ...]}.

    Every enemy_id from ENEMIES gets an entry — empty list when the
    enemy has no perk rows. Consumers use ENEMY_PERKS[eid] direct.
    """
    rows = _query("""
        SELECT enemy_id, perk_name AS name
        FROM enemy_perk
        ORDER BY enemy_id
    """)
    perks = {e['id']: [] for e in ENEMIES}
    for r in rows:
        perks[r['enemy_id']].append(r['name'])
    return perks


ENEMY_PERKS = load_enemy_perks()


def load_enemy_resistances():
    """Load enemy_skill_resistances into {enemy_id: {skill_id: mult}}.

    Every enemy_id from ENEMIES gets an entry — empty dict when the
    enemy has no resistance rows — plus 'custom', the synthetic
    Custom Brother enemy routes.py builds at request time, which has
    no DB rows. Consumers (routes.py) use ENEMY_RESISTANCES[eid]
    direct access per the NO GUARD RULE.
    """
    rows = _query('SELECT * FROM enemy_skill_resistance ORDER BY enemy_id')
    resistances = {e['id']: {} for e in ENEMIES}
    resistances['custom'] = {}
    for r in rows:
        resistances[r['enemy_id']][r['skill_id']] = r['multiplier']

    # Build skill ID -> name lookup for display
    skill_id_to_name = {s['id']: name for name, s in SKILLS.items()}
    skill_id_to_name.setdefault('skill.51_QUICK_SHOT', 'Quick Shot')
    skill_id_to_name.setdefault('skill.52_AIMED_SHOT', 'Aimed Shot')

    return resistances, skill_id_to_name


ENEMY_RESISTANCES, SKILL_ID_TO_NAME = load_enemy_resistances()


def load_attacker_buffs():
    """Load attacker buffs from MySQL."""
    rows = _query('SELECT * FROM attacker_buff ORDER BY sort_order')
    return [{'id': r['id'], 'name': r['name'], 'slug': r['unique_slug'],
             'stat': r['stat'], 'value': r['value']} for r in rows]


ATTACKER_BUFFS = load_attacker_buffs()


# Attach armor ranges and perks to each enemy
for e in ENEMIES:
    loadout = ARMOR_LOADOUTS.get(e['id'])
    if loadout:
        body_vals = [x['durability'] for x in loadout['body']]
        head_vals = [x['durability'] for x in loadout['helmet']]
        e['body_armor_min'] = min(body_vals) if body_vals else 0
        e['body_armor_max'] = max(body_vals) if body_vals else 0
        e['head_armor_min'] = min(head_vals) if head_vals else 0
        e['head_armor_max'] = max(head_vals) if head_vals else 0
        e['has_loadout'] = True
    else:
        e['body_armor_min'] = e['body_armor']
        e['body_armor_max'] = e['body_armor']
        e['head_armor_min'] = e['head_armor']
        e['head_armor_max'] = e['head_armor']
        e['has_loadout'] = False
    e['perks'] = ENEMY_PERKS[e['id']]
