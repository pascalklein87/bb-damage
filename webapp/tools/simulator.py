"""
Hits-to-kill Monte Carlo simulator. Wiki-side aggregation that wraps
single-hit calls to bb-damage-engine's attack module.

Lives here (not in bb-damage-engine) because:
  - The Monte Carlo loop, distribution buckets, kill-type tracking,
    peak first-hit calculation, and armor-loadout sampling are
    wiki-shaped concerns; the JS engine port has no counterpart.
  - The caller-side BB rules (bleed, injury, resolve, fearsome,
    Nine Lives, multi-hit orchestration) live with the simulator,
    not the engine.
  - Single caller: webapp/tools/routes.py.

Multi-hit shape (per bb-damage-engine/docs/multi_hit_caller.md):
  strategy='triple'    → Cascade / Hail: 3 sub-hits at 1/3 damage,
                         each rolls body part independently.
  strategy='split_man' → primary at 1.0× + secondary at 0.5× on
                         opposite body part with disable_headshot.
  else                 → 1 sub-hit (the normal single path).

Nine Lives is per-sub-hit for triple/single (CAN finish-kill on a
later sub-hit) and atomic on summed total for split_man (CANNOT
finish-kill).
"""
import math
import random
from collections import Counter

from bb_damage_engine import Defender, execute_attack, build_attacker


def _build_loadout_table(armor_loadouts):
    """Precompute body+head combinations with cumulative weights.
    `armor_loadouts=None` is a real product state (caller has no
    per-enemy loadout data). When provided, it MUST contain both
    'body' and 'helmet' keys with non-empty lists."""
    if armor_loadouts is None:
        return None
    body = armor_loadouts['body']
    head = armor_loadouts['helmet']
    if not body or not head:
        return None
    combos = []
    for b in body:
        for h in head:
            weight = b['percent'] * h['percent']
            combos.append((b['durability'], h['durability'], weight))
    total = sum(c[2] for c in combos)
    cumulative = []
    running = 0
    for body_dur, head_dur, w in combos:
        running += w / total
        cumulative.append((running, body_dur, head_dur))
    return cumulative


def _sample_loadout(table):
    """Pick a random body+head armor from the cumulative table."""
    r = random.random()
    for cum, body_dur, head_dur in table:
        if r <= cum:
            return body_dur, head_dur
    return table[-1][1], table[-1][2]


def simulate_hits_to_kill(attacker, defender, num_simulations,
                          headshot_chance, *,
                          executioner, crippling_strikes, head_hunter,
                          scales_with_missing_hp, calc_params,
                          enemy_perks, armor_loadouts, injury_immune,
                          skill_resistance, heal_per_turn):
    """
    Monte Carlo simulation: hits-to-kill distribution.

    attacker / defender: flat dicts (legacy bb-wiki shape).
    Internally builds Attacker / Defender records and calls
    execute_attack per hit.

    Caller-side rules (bleed, injury, resolve, fearsome, Nine Lives)
    are handled here, not by the engine.

    All keyword args are required — caller (routes.py) always emits a
    complete record. Per parent README NO GUARD RULE we don't accept
    None and coalesce; missing data is a producer bug.
    """

    # routes.py:expand_calculator_skills builds calc_params from
    # DEFAULT_CALC_PARAMS + per-skill overrides — every key below is
    # always present, so we read with direct access (NO GUARD RULE).
    strategy = calc_params['strategy']
    sub_count_for_strategy = (
        3 if strategy == 'triple' else
        2 if strategy == 'split_man' else
        1
    )

    bleed_per_turn       = calc_params['bleed_per_turn']
    force_body_part      = calc_params['force_body_part']
    no_headshot_bonus    = calc_params['no_headshot_bonus']
    added_headshot_bonus = calc_params['added_headshot_bonus']
    headshot_ap_add      = calc_params['headshot_ap_add']
    armor_damage_mult    = calc_params['armor_damage_mult']

    # Compose the BB modifier-name list. Routes.py passes the trait/perk
    # names from the UI checkboxes; skill-level effects (Chop, Puncture)
    # come from calc_params. Engine knows each name's numeric effect.
    modifier_names = list(attacker['modifiers'])
    if added_headshot_bonus == 0.5 and 'Chop' not in modifier_names:
        modifier_names.append('Chop')
    if no_headshot_bonus and 'Puncture' not in modifier_names:
        modifier_names.append('Puncture')

    is_melee_attack = attacker['is_melee_attack']

    has_battle_forged = 'Battle Forged' in enemy_perks
    has_steel_brow = 'Steel Brow' in enemy_perks
    has_nine_lives = 'Nine Lives' in enemy_perks
    has_nimble = 'Nimble' in enemy_perks
    has_resilient = 'Resilient' in enemy_perks

    # Engine-handled defender perks. Nimble's mult is precomputed by
    # the wiki (per-enemy hardcoded) and passed to the engine via its
    # named Defender.nimble_perc input (2026-07-02 engine API; the old
    # armor_fatigue field + 'Nimble' perk-name branch are gone).
    defender_perks_engine = []
    if has_battle_forged:
        defender_perks_engine.append('Battle Forged')
    if has_steel_brow:
        defender_perks_engine.append('Steel Brow')

    injury_threshold = 0.25
    gash_mult = calc_params['gash_injury_mult']
    if gash_mult:
        injury_threshold *= gash_mult
    if crippling_strikes:
        injury_threshold *= 0.66

    loadout_table = _build_loadout_table(armor_loadouts)

    # BB head/body forcing (bb_data force_body_part): 'body' never headshots
    # (Puncture), 'head' always headshots (Lash, Hail), 'none' rolls normally.
    if force_body_part == 'body':
        head_chance_perc = 0
    elif force_body_part == 'head':
        head_chance_perc = 100
    else:
        head_chance_perc = int(headshot_chance * 100)

    damage_min = attacker['damage_min']
    damage_max = attacker['damage_max']
    first_hit_combos = [(r, a)
                        for r in range(damage_min, damage_max + 1)
                        for a in range(damage_min, damage_max + 1)]
    runs_per_combo = max(4, math.ceil(num_simulations / len(first_hit_combos)))
    actual_simulations = len(first_hit_combos) * runs_per_combo

    nimble_mult_passthrough = defender['nimble_mult'] if has_nimble else 1.0

    results = []
    injury_results = []
    resolve_results = []
    fearsome_results = []
    damage_stats_runs = []

    for reg_roll, arm_roll in first_hit_combos:
      for _ in range(runs_per_combo):
        if loadout_table:
            current_body_armor, current_head_armor = _sample_loadout(loadout_table)
        else:
            current_body_armor = defender['armor']
            current_head_armor = defender['head_armor']
        current_hp = defender['hitpoints']
        max_hp = defender['hitpoints']
        is_injured = False
        nine_lives_used = False
        head_hunter_armed = False
        first_injury_hit = 0
        first_resolve_hit = 0
        first_fearsome_hit = 0
        bleed_stacks = []
        hits = 0
        first_hit_hp_dmg = 0
        first_hit_armor_dmg = 0
        max_hit_hp_dmg = 0
        max_hit_armor_dmg = 0
        kill_type = 'body'

        while current_hp > 0:
            hits += 1

            if bleed_stacks:
                current_hp -= len(bleed_stacks) * bleed_per_turn
                bleed_stacks = [t - 1 for t in bleed_stacks if t > 1]
            if heal_per_turn > 0 and current_hp > 0:
                current_hp = min(max_hp, current_hp + heal_per_turn)
            if current_hp <= 0:
                kill_type = 'bleed'
                break

            # Multi-hit attack: 1 / 2 / 3 sub-hits per BB skill identity.
            # See bb-damage-engine/docs/multi_hit_caller.md.
            sub_count = sub_count_for_strategy
            primary_body_part = None
            attack_hp_dmg = 0
            attack_armor_dmg = 0
            max_single_hit_hp = 0
            max_sub_hit_was_headshot = False
            last_sub_hit_was_headshot = False

            for i in range(sub_count):
                # Per-sub-hit damage scaling per multi_hit_caller.md.
                sub_damage_mult = (
                    0.333 if strategy == 'triple' else
                    0.5   if strategy == 'split_man' and i == 1 else
                    1.0
                )
                # Split Man secondary: clear head_hunter_armed; BB's
                # hand-rolled hitInfo bypasses HH's HitChance forcing.
                secondary = strategy == 'split_man' and i == 1

                sub_atk = build_attacker(
                    damage_min=damage_min,
                    damage_max=damage_max,
                    weapon_armor_damage_perc=attacker['damage_armor_perc'] * armor_damage_mult,
                    weapon_piercing_perc=attacker['piercing_perc'],
                    skill_damage_perc=attacker['damage_total_perc'] * sub_damage_mult,
                    skill_head_chance_perc=head_chance_perc,
                    skill_id='decapitate' if scales_with_missing_hp else None,
                    hitpoint_damage_minimum=attacker['hitpoint_damage_minimum'],
                    headshot_ap_add=headshot_ap_add,
                    is_melee_attack=is_melee_attack,
                    head_hunter_armed=False if secondary else head_hunter_armed,
                    modifiers=modifier_names,
                )

                sub_dfn = Defender(
                    body_armor_current=int(current_body_armor),
                    head_armor_current=int(current_head_armor),
                    hitpoints_current=current_hp,
                    hitpoints_max=max_hp,
                    perks=defender_perks_engine,
                    nimble_perc=nimble_mult_passthrough,
                    damage_regular_received_perc=1.0,
                    skill_resistance_perc=skill_resistance,
                    is_injured=is_injured,
                    # The wiki simulator does not model these — passed
                    # explicitly at their no-effect values (the engine has
                    # NO DEFAULTS; every Defender field is required).
                    damage_armor_received_perc=1.0,
                    damage_total_received_perc=1.0,
                    damage_piercing_received_perc=1.0,
                    regular_damage_reduction=0,
                    armor_damage_reduction=0,
                    damage_melee_received_perc=1.0,
                    damage_ranged_received_perc=1.0,
                    damage_body_direct_received_perc=1.0,
                    bone_plating_armed=False,
                )

                # Stratified rolls only on the very first sub-hit of the
                # very first attack (Monte Carlo first-hit enumeration).
                if hits == 1 and i == 0:
                    regular_roll = reg_roll
                    armor_roll = arm_roll
                else:
                    regular_roll = random.randint(damage_min, damage_max)
                    armor_roll = random.randint(damage_min, damage_max)

                # Body-part roll: calibrated for split_man secondary
                # (0 = head, 99 = body) so it lands opposite of primary.
                if secondary:
                    body_part_roll = 99 if primary_body_part == 'head' else 0
                else:
                    body_part_roll = random.randint(0, 99)

                result = execute_attack(
                    sub_atk, sub_dfn,
                    (regular_roll, armor_roll, body_part_roll),
                    disable_headshot=secondary,
                )

                if i == 0:
                    primary_body_part = result.body_part

                if result.body_part == 'head':
                    current_head_armor = result.armor_after
                else:
                    current_body_armor = result.armor_after
                current_hp -= result.hp_removed

                attack_hp_dmg += result.hp_removed
                attack_armor_dmg += result.armor_damage_dealt
                if result.hp_removed > max_single_hit_hp:
                    max_single_hit_hp = result.hp_removed
                    max_sub_hit_was_headshot = result.headshot
                last_sub_hit_was_headshot = result.headshot

                # Per-sub-hit injury check (BB onDamageReceived per hit).
                if (not injury_immune and not is_injured
                        and max_hp > 0 and result.hp_removed > 0):
                    eff_threshold = injury_threshold * (1.25 if result.headshot else 1.0)
                    if result.hp_removed / max_hp >= eff_threshold:
                        is_injured = True
                        first_injury_hit = hits

                # Nine Lives — single block covering both per-sub-hit
                # (triple/single) and atomic-on-summed-total (split_man,
                # gated to fire only on the last iteration).
                if ((strategy != 'split_man' or i == sub_count - 1)
                        and current_hp <= 0 and not nine_lives_used
                        and has_nine_lives):
                    current_hp = random.randint(11, 15)
                    bleed_stacks = []
                    nine_lives_used = True

                # Triple/single: stop if defender truly dead. Split Man
                # does NOT break — secondary fires regardless of primary.
                if strategy != 'split_man' and current_hp <= 0:
                    break

            if current_hp <= 0:
                kill_type = 'head' if last_sub_hit_was_headshot else 'body'

            head_hunter_armed = (head_hunter and last_sub_hit_was_headshot)

            if hits == 1:
                first_hit_hp_dmg = attack_hp_dmg
                first_hit_armor_dmg = attack_armor_dmg
            max_hit_hp_dmg = max(max_hit_hp_dmg, attack_hp_dmg)
            max_hit_armor_dmg = max(max_hit_armor_dmg, attack_armor_dmg)

            # Bleed application: BB rule is per-skill (Cleave/Gash/Rupture
            # apply via their own onTargetHit). Cascade/Hail/Split Man do
            # NOT apply bleed. Wiki's simplified single-hit threshold is
            # preserved for non-multi-hit skills only.
            if (strategy not in ('triple', 'split_man')
                    and bleed_per_turn > 0
                    and max_single_hit_hp >= 6):
                bleed_stacks.append(1 if has_resilient else 2)

            # Resolve / Fearsome — fire on the first attack where any
            # sub-hit's hp_removed crosses the threshold (BB checks per
            # onDamageReceived, so any sub-hit qualifies).
            if first_resolve_hit == 0 and max_single_hit_hp >= 15:
                first_resolve_hit = hits
            if first_fearsome_hit == 0 and max_single_hit_hp >= 1:
                first_fearsome_hit = hits

            if hits > 100:
                break

        results.append(hits)
        injury_results.append(first_injury_hit)
        resolve_results.append(first_resolve_hit)
        fearsome_results.append(first_fearsome_hit)
        damage_stats_runs.append({
            'first_hit_hp': first_hit_hp_dmg,
            'first_hit_armor': first_hit_armor_dmg,
            'max_hit_hp': max_hit_hp_dmg,
            'max_hit_armor': max_hit_armor_dmg,
            'body_armor_remaining': max(0, round(current_body_armor)),
            'head_armor_remaining': max(0, round(current_head_armor)),
            'kill_type': kill_type,
        })

    total = len(results)

    def _build_dist(data):
        """Always returns (list, stats|None). Empty input → ([], None)
        so consumers read with direct access (no `or []` fallback)."""
        valid = [r for r in data if r > 0]
        if not valid:
            return [], None
        counts = Counter(valid)
        dist = [{'hits': h, 'percent': max(0.1, round(counts[h] / total * 100, 1))}
                for h in sorted(counts.keys())]
        stats = {
            'avg': round(sum(valid) / len(valid), 2),
            'min': min(valid),
            'max': max(valid),
            'chance': max(0.1, round(len(valid) / total * 100, 1)),
        }
        return dist, stats

    kill_dist, _ = _build_dist(results)
    injury_dist, injury_stats = _build_dist(injury_results)
    resolve_dist, resolve_stats = _build_dist(resolve_results)
    fearsome_dist, fearsome_stats = _build_dist(fearsome_results)

    # Deterministic peak first-hit (max rolls vs weakest loadout).
    min_body_armor = defender['armor']
    min_head_armor = defender['head_armor']
    if armor_loadouts is not None:
        body_vals = [x['durability'] for x in armor_loadouts['body']]
        head_vals = [x['durability'] for x in armor_loadouts['helmet']]
        if body_vals:
            min_body_armor = min(body_vals)
        if head_vals:
            min_head_armor = min(head_vals)

    # Deterministic peak iterates the same multi-hit loop with max
    # rolls and primary forced to body or head. Per-sub-hit damages
    # accumulate; pick the higher of the two cases.
    # Only consider the body parts the skill can actually hit.
    if force_body_part == 'body':
        peak_cases = [(False, 'body')]
    elif force_body_part == 'head':
        peak_cases = [(True, 'head')]
    else:
        peak_cases = [(False, 'body'), (True, 'head')]
    peak_results = {}
    for is_head, label in peak_cases:
        peak_head_chance = 100 if is_head else 0
        peak_body_armor = int(min_body_armor)
        peak_head_armor = int(min_head_armor)
        peak_hp_state = defender['hitpoints']
        peak_total_hp = 0
        peak_total_armor = 0
        peak_primary_body_part = None

        for i in range(sub_count_for_strategy):
            sub_damage_mult = (
                0.333 if strategy == 'triple' else
                0.5   if strategy == 'split_man' and i == 1 else
                1.0
            )
            secondary = strategy == 'split_man' and i == 1
            peak_atk = build_attacker(
                damage_min=damage_min,
                damage_max=damage_max,
                weapon_armor_damage_perc=attacker['damage_armor_perc'] * armor_damage_mult,
                weapon_piercing_perc=attacker['piercing_perc'],
                skill_damage_perc=attacker['damage_total_perc'] * sub_damage_mult,
                skill_head_chance_perc=peak_head_chance,
                skill_id='decapitate' if scales_with_missing_hp else None,
                hitpoint_damage_minimum=attacker['hitpoint_damage_minimum'],
                headshot_ap_add=headshot_ap_add,
                is_melee_attack=is_melee_attack,
                head_hunter_armed=False,
                modifiers=modifier_names,
            )
            peak_dfn = Defender(
                body_armor_current=peak_body_armor,
                head_armor_current=peak_head_armor,
                hitpoints_current=peak_hp_state,
                hitpoints_max=defender['hitpoints'],
                perks=defender_perks_engine,
                nimble_perc=nimble_mult_passthrough,
                damage_regular_received_perc=1.0,
                skill_resistance_perc=skill_resistance,
                # Not modelled by the deterministic peak — explicit
                # no-effect values (engine has NO DEFAULTS).
                is_injured=False,
                damage_armor_received_perc=1.0,
                damage_total_received_perc=1.0,
                damage_piercing_received_perc=1.0,
                regular_damage_reduction=0,
                armor_damage_reduction=0,
                damage_melee_received_perc=1.0,
                damage_ranged_received_perc=1.0,
                damage_body_direct_received_perc=1.0,
                bone_plating_armed=False,
            )
            if secondary:
                body_part_roll = 99 if peak_primary_body_part == 'head' else 0
            else:
                body_part_roll = 0  # head_chance is 100 or 0; roll arbitrary
            peak = execute_attack(
                peak_atk, peak_dfn,
                (damage_max, damage_max, body_part_roll),
                disable_headshot=secondary,
            )
            if i == 0:
                peak_primary_body_part = peak.body_part
            if peak.body_part == 'head':
                peak_head_armor = peak.armor_after
            else:
                peak_body_armor = peak.armor_after
            peak_hp_state -= peak.hp_removed
            peak_total_hp += peak.hp_removed
            peak_total_armor += peak.armor_damage_dealt

        peak_results[label] = {
            'hp_removed':         peak_total_hp,
            'armor_damage_dealt': peak_total_armor,
        }

    peak_hp = max(v['hp_removed'] for v in peak_results.values())
    peak_armor = max(v['armor_damage_dealt'] for v in peak_results.values())

    damage_stats = {}
    if damage_stats_runs:
        damage_stats = {
            'max_first_hit_hp': peak_hp,
            'max_any_hit_hp': max(r['max_hit_hp'] for r in damage_stats_runs),
            'max_first_hit_armor': peak_armor,
            'max_any_hit_armor': max(r['max_hit_armor'] for r in damage_stats_runs),
            'avg_body_armor_remaining': round(sum(r['body_armor_remaining'] for r in damage_stats_runs) / total),
            'avg_head_armor_remaining': round(sum(r['head_armor_remaining'] for r in damage_stats_runs) / total),
            'kill_body_pct': round(sum(1 for r in damage_stats_runs if r['kill_type'] == 'body') / total * 100, 1),
            'kill_head_pct': round(sum(1 for r in damage_stats_runs if r['kill_type'] == 'head') / total * 100, 1),
            'kill_bleed_pct': round(sum(1 for r in damage_stats_runs if r['kill_type'] == 'bleed') / total * 100, 1),
        }

    return {
        'avg_hits_to_kill': round(sum(results) / total, 2),
        'distribution': kill_dist,
        'injury': injury_stats,
        'injury_distribution': injury_dist,
        'resolve': resolve_stats,
        'resolve_distribution': resolve_dist,
        'fearsome': fearsome_stats,
        'fearsome_distribution': fearsome_dist,
        'damage_stats': damage_stats,
        'actual_simulations': actual_simulations,
    }
