"""
Load weapon and enemy data for the damage calculator.

Reference data is READ FROM bb_data, the canonical BB extraction:
  - bb_data.item_weapon             weapon stats
  - bb_data.weapon_skill            skill mechanics (base + mastery via mastery_class)
  - bb_data.weapon_skill_connection which skills each weapon has, in order

This app's own bb_damage DB keeps only what bb_data does not carry:
  - weapon(id, name, unique_slug)          the curated calculator weapons + display name/slug
  - weapon_skill_display(name, is_mastery, label, damage_calculator_tooltip)
                                            calculator-authored hover text, per skill concept
  - enemy / enemy_armor_loadout / enemy_perk / enemy_skill_resistance
  - attacker_buff / cache

Only DAMAGE skills (bb_data.weapon_skill.damage_perc > 0) are listed; utility
skills (Reload, Disarm, Hook, Repel) are excluded by that filter.
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
    """Producer-side normalisation: a NULL DB value becomes the canonical
    'absent' value. Used only where NULL is a real product state (an
    unfactioned weapon, an enemy with no racial trait), never to mask a
    missing required field."""
    return default if v is None else v


def _slug(name):
    """Weapon / skill URL slug. Deterministic from the display name; the
    skill form matches the SKILL_CALC_PARAMS keys in routes.py (e.g.
    'Gash' -> 'gash', 'Split Man' -> 'split-man', mastery adds '-mastery')."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).rstrip('-')


def _skill_dict(r, display):
    """Build a calculator skill dict from a bb_data connection+skill row.

    `display` maps (skill name, is_mastery) -> (label, tooltip). A skill
    with no display row (e.g. a skill the wiki never annotated) shows no
    hint; the hint is optional UI text, not a required field.
    """
    is_mastery = bool(r['is_mastery'])
    name = r['skill_name'] + (' (Mastery)' if is_mastery else '')
    slug = _slug(r['skill_name']) + ('-mastery' if is_mastery else '')
    d = display.get((r['skill_name'], 1 if is_mastery else 0))
    label, tooltip = (d['label'], d['tooltip']) if d else ('', '')
    return {
        'id': r['skill_id'],
        'name': name,
        'slug': slug,
        'ap_cost': r['action_cost'],
        'stamina_cost': r['fatigue_base_cost'],
        # Non-attack skills (Riposte, Spearwall) carry piercing_perc_bonus 0
        # in bb_data, so this is 0.0 for them - a number, not None.
        'piercing_perc': r['piercing_perc_bonus'] / 100.0,
        'bonus_damage': r['damage_bonus'],
        'damage_mult': r['damage_perc'] / 100.0,
        'headshot_bonus': 0.0,
        'label': label,
        'damage_calculator_tooltip': tooltip,
        'bleed_per_turn': r['bleed_per_turn'],
        # Demolish Armor's 10 HP floor is wired through SKILL_CALC_PARAMS in
        # routes.py, not a per-skill column.
        'hitpoint_damage_minimum': 0,
        'scales_with_missing_hp': bool(r['damage_scales_with_missing_hp']),
        # BB head/body forcing: 'body' = never headshots (Puncture),
        # 'head' = always headshots (Lash, Hail), 'none' = normal roll.
        'force_body_part': r['force_body_part'],
        'is_mastery': is_mastery,
    }


def load_weapons():
    """Load the calculator weapons with base+mastery damage skills attached.

    Weapon stats come from bb_data.item_weapon; skills and their order come
    from bb_data.weapon_skill_connection; only display name/slug come from
    this app's own `weapon` table.
    """
    weapons_rows = _query("""
        SELECT w.id, w.name, w.unique_slug,
               iw.is_two_handed, iw.mastery, iw.damage_min, iw.damage_max,
               iw.piercing_perc, iw.armor_damage_perc, iw.shield_damage,
               iw.headshot_chance_bonus, iw.fatigue_per_use, iw.subfaction
        FROM weapon w
        JOIN bb_data.item_weapon iw ON iw.id = w.id
        ORDER BY w.name
    """)

    display = {(r['name'], r['is_mastery']): {'label': r['label'],
               'tooltip': r['damage_calculator_tooltip'],
               'show': r['show_in_calculator']}
               for r in _query("SELECT name, is_mastery, label, "
                               "damage_calculator_tooltip, show_in_calculator "
                               "FROM weapon_skill_display")}

    # Every damage skill connected to a calc weapon, base then its mastery,
    # ordered as the weapon lists them.
    conn_rows = _query("""
        SELECT c.weapon_id, c.sort_order, s.id AS skill_id, s.name AS skill_name,
               (s.mastery_class IS NOT NULL) AS is_mastery,
               s.action_cost, s.fatigue_base_cost, s.range_min, s.range_max,
               s.piercing_perc_bonus, s.damage_perc, s.damage_bonus,
               s.bleed_per_turn, s.damage_scales_with_missing_hp, s.force_body_part
        FROM bb_data.weapon_skill_connection c
        JOIN bb_data.weapon_skill s ON s.id = c.weapon_skill_id
        WHERE c.weapon_id IN (SELECT id FROM weapon) AND s.damage_perc > 0
        ORDER BY c.weapon_id, c.sort_order, (s.mastery_class IS NOT NULL)
    """)
    skills_by_weapon = {}
    for r in conn_rows:
        d = display.get((r['skill_name'], 1 if r['is_mastery'] else 0))
        if r['is_mastery']:
            # A mastery is shown only when weapon_skill_display flags it. That
            # flagged set is the curated list of masteries that change the
            # calc's output - either a damage column (Cleave bleed 5->10,
            # Destroy Armor x1.5->x2.0, Shoot Bolt piercing) or an effect with
            # no bb_data column of its own that lives in the tooltip (Gash's
            # lower injury threshold, Pound's head piercing). A mastery that
            # only cuts AP or changes hit chance / range deals identical
            # damage and is not shown.
            if d is None or not d['show']:
                continue
        elif d is not None and not d['show']:
            # A base skill shows unless explicitly excluded (Split Shield,
            # which only damages shields, not the enemy).
            continue
        skills_by_weapon.setdefault(r['weapon_id'], []).append(_skill_dict(r, display))

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
            'subfaction': _coalesce(r['subfaction'], ''),
            'slug': r['unique_slug'],
            'fatigue_per_use': r['fatigue_per_use'],
            'skills': skills_by_weapon.get(r['id'], []),
        })
    return weapons


def load_enemies():
    """Load enemies from the app's own enemy table (no bb_data equivalent)."""
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


def load_enemy_perks():
    """Load enemy_perks into {enemy_id: [perk_name, ...]}.

    Every enemy_id from ENEMIES gets an entry - empty list when the
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


def load_enemy_resistances():
    """Load enemy_skill_resistances into {enemy_id: {skill_slug: mult}}.

    Keyed by skill slug (the same slug _skill_dict emits), so routes.py
    looks a selected skill up directly by its slug. Every enemy_id from
    ENEMIES gets an entry - empty dict when the enemy has no resistance
    rows - plus 'custom', the synthetic Custom Brother routes.py builds
    at request time.
    """
    rows = _query('SELECT enemy_id, skill_id, multiplier FROM enemy_skill_resistance ORDER BY enemy_id')
    resistances = {e['id']: {} for e in ENEMIES}
    resistances['custom'] = {}
    for r in rows:
        resistances[r['enemy_id']][r['skill_id']] = r['multiplier']

    # slug -> display name for the racial-resistance panel
    name_rows = _query("""
        SELECT DISTINCT s.name
        FROM bb_data.weapon_skill_connection c
        JOIN bb_data.weapon_skill s ON s.id = c.weapon_skill_id
        WHERE c.weapon_id IN (SELECT id FROM weapon) AND s.damage_perc > 0
    """)
    slug_to_name = {_slug(r['name']): r['name'] for r in name_rows}
    return resistances, slug_to_name


def load_attacker_buffs():
    """Load attacker buffs from the app's own attacker_buff table."""
    rows = _query('SELECT * FROM attacker_buff ORDER BY sort_order')
    return [{'id': r['id'], 'name': r['name'], 'slug': r['unique_slug'],
             'stat': r['stat'], 'value': r['value']} for r in rows]


# Load on import
WEAPONS = load_weapons()
ENEMIES = load_enemies()
ARMOR_LOADOUTS = load_armor_loadouts()
ENEMY_PERKS = load_enemy_perks()
ENEMY_RESISTANCES, SKILL_SLUG_TO_NAME = load_enemy_resistances()
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
