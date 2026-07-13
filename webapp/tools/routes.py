import re

from flask import Blueprint, render_template, request
from bb_engine import nimble_multiplier
from engine.cache import get_cached, set_cached
from .simulator import simulate_hits_to_kill
from engine.data import (WEAPONS, ENEMIES, ARMOR_LOADOUTS,
                         ENEMY_RESISTANCES, SKILLS,
                         SKILL_ID_TO_NAME, ATTACKER_BUFFS)

tools_bp = Blueprint('tools', __name__, url_prefix='/damage-calculator')


def _to_slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).rstrip('-')


# Modifier metadata: URL slug -> { checkbox: DOM input id, name: BB
# trait/perk name the engine recognises }. The numeric effect of each
# name lives in bb-engine (bb_engine.attack.build_attacker), not here.
MODIFIERS = {
    'double-grip':       {'checkbox': 'trait-double-grip',       'name': 'Double Grip'},
    'drunkard':          {'checkbox': 'trait-drunkard',          'name': 'Drunkard'},
    'huge':              {'checkbox': 'trait-huge',              'name': 'Huge'},
    'tiny':              {'checkbox': 'trait-tiny',              'name': 'Tiny'},
    'brute':             {'checkbox': 'trait-brute',             'name': 'Brute'},
    'duelist':           {'checkbox': 'perk-duelist',            'name': 'Duelist'},
    'killing-frenzy':    {'checkbox': 'perk-killing-frenzy',     'name': 'Killing Frenzy'},
    'executioner':       {'checkbox': 'perk-executioner',        'name': 'Executioner'},
    'head-hunter':       {'checkbox': 'perk-head-hunter',        'name': 'Head Hunter'},
    'crippling-strikes': {'checkbox': 'perk-crippling-strikes',  'name': 'Crippling Strikes'},
    'juggler':           {'checkbox': 'trait-juggler',           'name': 'Juggler'},
    'killer-on-the-run': {'checkbox': 'trait-killer-on-the-run', 'name': 'Killer on the Run'},
    'broken-arm':        {'checkbox': 'injury-broken-arm',       'name': 'Broken Arm'},
    'split-shoulder':    {'checkbox': 'injury-split-shoulder',   'name': 'Split Shoulder'},
    'cut-arm-sinew':     {'checkbox': 'injury-cut-arm-sinew',    'name': 'Cut Arm Sinew'},
    'injured-shoulder':  {'checkbox': 'injury-injured-shoulder', 'name': 'Injured Shoulder'},
    'dazed':             {'checkbox': 'status-dazed',            'name': 'Dazed'},
    'distracted':        {'checkbox': 'status-distracted',       'name': 'Distracted'},
    'strange-mushrooms': {'checkbox': 'status-strange-mushrooms','name': 'Strange Mushrooms'},
}


# ---------------------------------------------------------------------------
# Calculator-specific simulation parameters, keyed by skill slug.
# Only behaviour the simulation needs but the DB does not store.
# Core stats (piercing, damage, bleed, AP, fatigue) come from the DB.
# ---------------------------------------------------------------------------

SKILL_CALC_PARAMS = {
    'gash':                   {'gash_injury_mult': 0.66},
    'gash-mastery':           {'gash_injury_mult': 0.50},
    'destroy-armor':          {'armor_damage_mult': 1.50},
    'destroy-armor-mastery':  {'armor_damage_mult': 2.00},
    'demolish-armor':         {'armor_damage_mult': 1.45},
    'demolish-armor-mastery': {'armor_damage_mult': 1.93},
    'pound':                  {'headshot_ap_add': 0.10},
    'pound-mastery':          {'headshot_ap_add': 0.20},
    'puncture':               {'no_headshot_bonus': True},
    'puncture-mastery':       {'no_headshot_bonus': True},
    'chop':                   {'added_headshot_bonus': 0.50},
    'lash':                   {'always_headshot': True},
    'lash-mastery':           {'always_headshot': True},
    'cascade':                {'strategy': 'triple'},
    'hail':                   {'strategy': 'triple', 'always_headshot': True},
    'hail-mastery':           {'strategy': 'triple', 'always_headshot': True},
    'split-man':              {'strategy': 'split_man'},
}




THROW_SLUGS = frozenset([
    'throw-javelin', 'throw-axe', 'throw-spear', 'throw-bola',
])


# Per parent README NO GUARD RULE: every skill's calc_params dict
# carries every documented field, so simulator.py can read with direct
# access (no .get(k, default)). Per-skill SKILL_CALC_PARAMS overrides
# layer on top.
DEFAULT_CALC_PARAMS = {
    'strategy':             'single',
    'bleed_per_turn':       0,
    'always_headshot':      False,
    'no_headshot_bonus':    False,
    'added_headshot_bonus': 0,
    'headshot_ap_add':      0,
    'armor_damage_mult':    1.0,
    'gash_injury_mult':     0,
}


def expand_calculator_skills(weapons):
    """Attach calc_params to DB skills and create throwing mastery variants."""
    result = []
    for w in weapons:
        skills = []

        for skill in w['skills']:
            slug = skill['slug']

            # Build a complete calc_params: defaults + per-skill overrides.
            params = dict(DEFAULT_CALC_PARAMS)
            if slug in SKILL_CALC_PARAMS:
                params.update(SKILL_CALC_PARAMS[slug])
            # Bleed-per-turn defaults to the skill's DB value when the
            # SKILL_CALC_PARAMS entry didn't override it.
            if skill['bleed_per_turn'] > 0 and params['bleed_per_turn'] == 0:
                params['bleed_per_turn'] = skill['bleed_per_turn']

            s = dict(skill)
            s['calc_params'] = params
            skills.append(s)

            # Throwing weapons: add mastery variants at 3t and 2t range
            if slug in THROW_SLUGS:
                for suffix, label, mult in [(' 3t', 'Mastery, x120%', 1.20),
                                             (' 2t', 'Mastery, x130%', 1.30)]:
                    vs = dict(s)
                    vs['name'] = s['name'] + suffix
                    vs['slug'] = slug + suffix.strip()
                    vs['label'] = label
                    vs['damage_mult'] = mult
                    vs['calc_params'] = dict(s['calc_params'])
                    skills.append(vs)

        result.append(dict(w, skills=skills))
    return result


def tag_weapon_names(weapons):
    """Add faction + handedness tags to weapons for searchability."""
    result = []
    for w in weapons:
        hand = '2H' if w['two_handed'] else '1H'
        faction = w['subfaction']  # always str ('' if unfactioned)
        tag = ('%s %s' % (faction, hand)).strip() if faction else hand
        result.append(dict(w, tag=tag))
    return result


def _enrich_enemies(enemies):
    """Attach racial trait data to each enemy for template."""
    result = []
    for e in enemies:
        eid = e['id']
        immunities = []
        if e.get('is_bleed_immune'):
            immunities.append('Immune to Bleeding')
        if e.get('is_injury_immune'):
            immunities.append('Immune to Injuries')
        if e.get('is_morale_immune'):
            immunities.append('Immune to Morale')
        if e.get('armor_damage_received_perc', 1.0) != 1.0:
            pct = int(round((1.0 - e['armor_damage_received_perc']) * 100))
            immunities.append(f'Armor takes {pct}% less damage')
        enemy_res = ENEMY_RESISTANCES[eid]
        res_list = []
        if enemy_res:
            for sid, mult in sorted(enemy_res.items(), key=lambda x: x[1]):
                sname = SKILL_ID_TO_NAME.get(sid, sid)
                res_list.append({'skill': sname, 'percent': int(round(mult * 100))})
        result.append(dict(e,
                           racial_resistances=res_list,
                           racial_immunities=immunities))
    return result


@tools_bp.route('/cache')
def cache_view():
    import json as _json
    from engine.db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, hash, json, url, count, last_used, num_simulations FROM cache ORDER BY last_used DESC')
    raw = cursor.fetchall()
    cursor.close()
    conn.close()
    rows = []
    for r in raw:
        parsed = _json.loads(r['json'])
        rows.append({
            'id': r['id'],
            'hash': r['hash'],
            'url': r['url'],
            'json_size': len(r['json']),
            'avg_hits': parsed['avg_hits_to_kill'],
            'count': r['count'],
            'last_used': r['last_used'],
            'num_simulations': r['num_simulations'],
        })
    return render_template('tools/cache_view.html', rows=rows)


def _calc_input_error(message):
    """400 page for malformed calculator URLs (unknown slugs, invalid
    skill/weapon combos). Producer bugs (incomplete bb_data) still
    raise per the NO GUARD RULE."""
    return render_template('tools/calc_error.html', message=message), 400


@tools_bp.route('', strict_slashes=False)
def damage_calculator():
    calc_weapons = expand_calculator_skills(WEAPONS)
    calc_weapons = tag_weapon_names(calc_weapons)
    calc_enemies = _enrich_enemies(ENEMIES)

    weapon_slug = request.args.get('weapon', 'greatsword')
    enemy_slug = request.args.get('enemy', 'barbarian-chosen')
    skill_slug = request.args.get('skill')
    mods_str = request.args.get('mods', '')
    active_mods = mods_str.split('_') if mods_str else []
    buff_slug = request.args.get('buff', '')
    champion = request.args.get('champion', '') == '1'

    # Find selected items by slug for template pre-selection
    sel_weapon = next((w for w in calc_weapons
                       if weapon_slug and w.get('slug') == weapon_slug),
                      None)
    # Custom brother defender
    is_custom_brother = (enemy_slug == 'custom-brother')
    if is_custom_brother:
        try:
            cb_hp = int(request.args.get('cb_hp', 80))
            cb_body = int(request.args.get('cb_body', 300))
            cb_head = int(request.args.get('cb_head', 300))
        except ValueError:
            return _calc_input_error(
                "the custom brother stats (cb_hp, cb_body, cb_head) "
                "must be whole numbers.")
        cb_perks_str = request.args.get('cb_perks', '')
        cb_perks = cb_perks_str.split('_') if cb_perks_str else []
        try:
            cb_armor_fatigue = int(request.args.get('cb_fat', 0))
        except ValueError:
            return _calc_input_error("cb_fat must be a whole number.")
        # Nimble damage-received multiplier - bb-engine's ONE Python home
        # (bb_engine.nimble_multiplier; BB perk_nimble.nut:69-70). No copied formula.
        cb_nimble_mult = nimble_multiplier(cb_armor_fatigue)

        cb_perk_names = []
        if 'bf' in cb_perks:
            cb_perk_names.append('Battle Forged')
        if 'nimble' in cb_perks:
            cb_perk_names.append('Nimble')
        if 'sb' in cb_perks:
            cb_perk_names.append('Steel Brow')
        if 'nl' in cb_perks:
            cb_perk_names.append('Nine Lives')
        if 'res' in cb_perks:
            cb_perk_names.append('Resilient')

        sel_enemy = {
            'id': 'custom',
            'name': 'Custom Brother',
            'slug': 'custom-brother',
            'hitpoints': cb_hp,
            'body_armor': cb_body,
            'head_armor': cb_head,
            'body_armor_min': cb_body,
            'body_armor_max': cb_body,
            'head_armor_min': cb_head,
            'head_armor_max': cb_head,
            'has_loadout': False,
            'is_bleed_immune': False,
            'is_injury_immune': False,
            'is_morale_immune': False,
            'racial_trait': '',
            'armor_damage_received_perc': 1.0,
            'heal_per_turn': 0,
            'perks': cb_perk_names,
            '_nimble_mult': cb_nimble_mult,
            '_indomitable': 'indom' in cb_perks,
        }
    else:
        sel_enemy = next((e for e in ENEMIES
                          if enemy_slug and e.get('slug') == enemy_slug),
                         None)

    sel_buff = next((b for b in ATTACKER_BUFFS if b.get('slug') == buff_slug), None)

    selected = {
        'weapon_id': sel_weapon['id'] if sel_weapon else None,
        'enemy_id': sel_enemy['id'] if sel_enemy else None,
        'skill_slug': skill_slug,
        'mods': active_mods,
        'mod_checkboxes': {MODIFIERS[s]['checkbox'] for s in active_mods
                           if s in MODIFIERS},
        'buff_slug': buff_slug,
        'champion': champion,
        'is_custom_brother': is_custom_brother,
    }


    if sel_weapon is None:
        return _calc_input_error(f"there is no weapon called {weapon_slug!r}.")
    if sel_enemy is None:
        return _calc_input_error(f"there is no enemy called {enemy_slug!r}.")

    weapon = sel_weapon
    enemy = sel_enemy

    # Resolve skill. When the URL specifies a skill slug it MUST exist
    # on the weapon — silent fallback used to mask malformed URLs (the
    # wiki landed on weapon['skills'][0] instead of erroring). When no
    # slug is provided, default to the weapon's first listed skill.
    if not weapon['skills']:
        raise ValueError(
            f"weapon {weapon['slug']!r} has no skills attached; "
            f"weapon_skill_map row missing in bb_data."
        )
    if skill_slug:
        skill = next((s for s in weapon['skills']
                      if s['slug'] == skill_slug), None)
        if skill is None:
            return _calc_input_error(
                f"the skill {skill_slug!r} is not available on the weapon "
                f"{weapon['slug']!r}. Its skills are: "
                f"{', '.join(s['slug'] for s in weapon['skills'])}."
            )
    else:
        skill = weapon['skills'][0]

    # Base weapon stats (overridable by edited params)
    has_edited_stats = request.args.get('dmin') is not None
    try:
        damage_min = int(request.args.get('dmin', weapon['damage_min']))
        damage_max = int(request.args.get('dmax', weapon['damage_max']))
        ap = float(request.args.get('ap', weapon['piercing_perc'] * 100)) / 100
        dap = float(request.args.get('dap', weapon['damage_armor_perc'] * 100)) / 100
        hs_param = request.args.get('hs')
        if hs_param is not None:
            headshot_chance = (25 + float(hs_param)) / 100
        else:
            headshot_chance = (25 + weapon['headshot_chance']) / 100.0
    except ValueError:
        return _calc_input_error(
            "the edited weapon stats (dmin, dmax, ap, dap, hs) must be "
            "numbers.")

    # Apply skill stats. expand_calculator_skills + _skill_dict
    # guarantee every field below is present on every skill dict, so
    # we read with direct access (no .get fallback). piercing_perc is
    # None for non-attack skills (Riposte / Spearwall) per
    # data.py:load_skills — that's a real product state, not a guard.
    damage_min += skill['bonus_damage']
    damage_max += skill['bonus_damage']
    if skill['piercing_perc'] is not None:
        ap = min(1.0, ap + skill['piercing_perc'])
    skill_damage_mult        = skill['damage_mult']
    scales_with_missing_hp   = skill['scales_with_missing_hp']
    hitpoint_damage_minimum  = skill['hitpoint_damage_minimum']
    calc_params              = skill['calc_params']
    skill_name               = skill['name']

    # Build the BB-engine modifier-name list. Skip 1H-only mods for
    # 2H and throwing weapons; engine handles all numeric values.
    is_two_handed = weapon['two_handed']
    is_thrown = weapon['mastery'] == 'throwing'
    modifier_names = []
    for mod in active_mods:
        if (is_two_handed or is_thrown) and mod in ('double-grip', 'duelist'):
            continue
        if skill_name == 'Puncture' and mod == 'double-grip':
            continue
        info = MODIFIERS.get(mod)
        if info:
            modifier_names.append(info['name'])

    executioner = 'executioner' in active_mods
    crippling_strikes = 'crippling-strikes' in active_mods
    head_hunter = 'head-hunter' in active_mods

    attacker = {
        'damage_min': damage_min,
        'damage_max': damage_max,
        'damage_armor_perc': dap,
        'piercing_perc': ap,
        'damage_regular_perc': 1.0,
        # skill-only base; modifier names compose into damage_perc inside
        # the engine via build_attacker.
        'damage_total_perc': skill_damage_mult,
        'hitpoint_damage_minimum': hitpoint_damage_minimum,
        'modifiers': modifier_names,
        'is_melee_attack': not is_thrown,
    }

    # Apply attacker buff
    if sel_buff:
        buff_mult = sel_buff['value'] / 100.0
        if sel_buff['stat'] == 'DamageTotalPerc':
            attacker['damage_total_perc'] *= buff_mult
        elif sel_buff['stat'] == 'DamageDirectPerc':
            attacker['piercing_perc'] = min(1.0, attacker['piercing_perc'] * buff_mult)
        elif sel_buff['stat'] == 'DamageArmorPerc':
            attacker['damage_armor_perc'] *= buff_mult

    # Apply champion buff (multiplicative, stacks on top)
    if champion:
        attacker['damage_total_perc'] *= 1.15

    bleed_immune = enemy['is_bleed_immune']
    injury_immune = enemy['is_injury_immune']

    # Nimble multiplier: precomputed from armor fatigue at max loadout.
    # Formula: fat = min(0, bodyFat + headFat + 15)
    #          mult = min(1.0, 0.4 + abs(fat)^1.23 * 0.01)
    NIMBLE_MULT = {
        'Conscript':      0.40,   # light armor, full benefit
        'Assassin':       0.40,   # always full benefit
        'Gladiator':      0.49,   # avg across loadouts
        'Nomad Leader':   0.55,   # avg across loadouts
        'Blade Dancer':   0.40,   # light armor
        'Desert Stalker': 0.40,   # light armor
    }

    # Nimble mult: only consulted when defender has Nimble. Custom
    # brother sets _nimble_mult during construction; vanilla enemies
    # are looked up in NIMBLE_MULT — missing entry for a Nimble enemy
    # is a producer bug (raises via dict access).
    if 'Nimble' in enemy['perks']:
        if is_custom_brother:
            nimble_mult_val = enemy['_nimble_mult']
        else:
            nimble_mult_val = NIMBLE_MULT[enemy['name']]
    else:
        nimble_mult_val = 1.0   # unused (engine only applies on Nimble)

    # Indomitable: halves all incoming damage. Only the custom brother
    # path can set this flag.
    total_received = 1.0
    if is_custom_brother and enemy.get('_indomitable'):
        total_received = 0.5

    defender = {
        'armor': enemy['body_armor_max'],
        'head_armor': enemy['head_armor_max'],
        'hitpoints': enemy['hitpoints'],
        'nimble_mult': nimble_mult_val,
        'damage_regular_received_perc': 1.0,
        'damage_armor_received_perc': enemy['armor_damage_received_perc'],
        'damage_piercing_received_perc': 1.0,
        'damage_total_received_perc': total_received,
        'regular_damage_reduction': 0,
        'armor_damage_reduction': 0,
    }

    num_simulations = 20000

    # Build canonical cache URL with sorted mods (same combo = same hash)
    cache_parts = [f'weapon={weapon_slug}', f'enemy={enemy_slug}']
    if skill_slug:
        cache_parts.append(f'skill={skill_slug}')
    if active_mods:
        cache_parts.append(f'mods={"_".join(sorted(active_mods))}')
    if has_edited_stats:
        cache_parts.append(f'dmin={damage_min}&dmax={damage_max}&ap={int(ap*100)}&dap={int(dap*100)}')
    if buff_slug:
        cache_parts.append(f'buff={buff_slug}')
    if champion:
        cache_parts.append('champion=1')
    if is_custom_brother:
        cache_parts.append(f'cb_hp={enemy["hitpoints"]}&cb_body={enemy["body_armor"]}&cb_head={enemy["head_armor"]}')
        cb_perks_str = request.args.get('cb_perks', '')
        if cb_perks_str:
            cache_parts.append(f'cb_perks={cb_perks_str}')
        if 'nimble' in (cb_perks_str.split('_') if cb_perks_str else []):
            cache_parts.append(f'cb_fat={cb_armor_fatigue}')
    cache_url = '&'.join(cache_parts)

    enemy_perks = enemy['perks']
    armor_loadouts = ARMOR_LOADOUTS.get(enemy['id'])

    # Bleed immunity: zero out bleed. expand_calculator_skills always
    # emits bleed_per_turn (0 when the skill doesn't bleed), so the
    # guard "in calc_params" is gone; we just check the value.
    if bleed_immune and calc_params['bleed_per_turn'] > 0:
        calc_params = dict(calc_params)
        calc_params['bleed_per_turn'] = 0

    # Skill-to-enemy resistance lookup
    skill_resistance = 1.0
    if skill and enemy:
        skill_id = skill.get('id', '')
        enemy_res = ENEMY_RESISTANCES[enemy['id']]
        skill_resistance = enemy_res.get(skill_id, 1.0)

    # Check cache
    cached = get_cached(cache_url)
    if cached:
        hits_to_kill = cached
    else:
        hits_to_kill = simulate_hits_to_kill(
            attacker, defender, num_simulations, headshot_chance,
            executioner=executioner,
            crippling_strikes=crippling_strikes,
            head_hunter=head_hunter,
            scales_with_missing_hp=scales_with_missing_hp,
            calc_params=calc_params,
            enemy_perks=enemy_perks,
            armor_loadouts=armor_loadouts,
            injury_immune=injury_immune,
            skill_resistance=skill_resistance,
            heal_per_turn=int(enemy['hitpoints'] * enemy['heal_per_turn'] / 100) if enemy['heal_per_turn'] > 0 else 0)

        # Strip data for immune enemies before caching
        morale_immune = enemy['is_morale_immune']
        if morale_immune:
            hits_to_kill['resolve'] = None
            hits_to_kill['resolve_distribution'] = None
            hits_to_kill['fearsome'] = None
            hits_to_kill['fearsome_distribution'] = None
        if injury_immune:
            hits_to_kill['injury'] = None
            hits_to_kill['injury_distribution'] = None

        set_cached(cache_url, hits_to_kill,
                   num_simulations=hits_to_kill['actual_simulations'])

    # Count armor combinations
    armor_combos = 0
    if armor_loadouts is not None:
        body_count = len(armor_loadouts['body'])
        head_count = len(armor_loadouts['helmet'])
        armor_combos = body_count * head_count

    # Build racial trait info for modal
    racial_trait_name = enemy['racial_trait']
    enemy_res = ENEMY_RESISTANCES[enemy['id']]
    racial_resistances = []
    if enemy_res:
        for sid, mult in sorted(enemy_res.items(),
                                key=lambda x: x[1]):
            sname = SKILL_ID_TO_NAME.get(sid, sid)
            racial_resistances.append({
                'skill': sname,
                'mult': mult,
                'percent': int(round(mult * 100)),
            })
    racial_immunities = []
    if enemy['is_bleed_immune']:
        racial_immunities.append('Immune to Bleeding')
    if enemy['is_injury_immune']:
        racial_immunities.append('Immune to Injuries')
    if enemy['is_morale_immune']:
        racial_immunities.append('Immune to Morale')
    if enemy['armor_damage_received_perc'] != 1.0:
        pct = int(round((1.0 - enemy['armor_damage_received_perc']) * 100))
        racial_immunities.append(f'Armor takes {pct}% less damage')


    results = {
        'hits_to_kill': hits_to_kill,
        'enemy_name': enemy['name'],
        'weapon_name': weapon['name'],
        'injury_immune': injury_immune,
        'morale_immune': enemy['is_morale_immune'],
        'enemy_perk': enemy_perks,
        'armor_combos': armor_combos,
        'num_simulations': hits_to_kill['actual_simulations'],
        'racial_trait': racial_trait_name,
        'racial_resistances': racial_resistances,
        'racial_immunities': racial_immunities,
        'skill_resistance': skill_resistance,
        'buff_name': sel_buff['name'] if sel_buff else None,
        'champion': champion,
    }

    return render_template('tools/damage_calculator.html',
                           weapons=calc_weapons, enemies=calc_enemies,
                           results=results, selected=selected,
                           sel_weapon=sel_weapon, sel_enemy=sel_enemy,
                           attacker_buffs=ATTACKER_BUFFS)
