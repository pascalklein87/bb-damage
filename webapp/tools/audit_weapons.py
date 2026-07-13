"""
Audit all weapons against BB vanilla source.
Checks skill mappings and reports mismatches.

Usage:
    cd bb-wiki/
    python -m tools.audit_weapons
"""
import os
import re

from engine.db import get_connection
BB_WEAPONS = '../external/bb-vanilla-data/data_001/scripts/items/weapons'

# Map BB skill script names to our DB skill names
SKILL_NAME_MAP = {
    'stab': 'Stab', 'puncture': 'Puncture', 'deathblow_skill': 'Deathblow',
    'slash': 'Slash', 'riposte': 'Riposte', 'gash': 'Gash',
    'chop': 'Chop', 'split_shield': 'Split Shield',
    'cleave': 'Cleave', 'decapitate': 'Decapitate',
    'overhead_strike': 'Overhead Strike',
    'split': 'Split (Sword)', 'split_axe': 'Split (Axe)',
    'swing': 'Swing', 'round_swing': 'Round Swing',
    'bash': 'Bash', 'knock_out': 'Knock Out',
    'crush_armor': 'Destroy Armor', 'batter': 'Batter',
    'flail': 'Flail', 'lash': 'Lash',
    'thrust': 'Thrust', 'spearwall': 'Spearwall',
    'impale': 'Impale', 'repel': 'Repel', 'hook': 'Hook',
    'split_man': 'Split Man', 'rupture': 'Rupture',
    'quick_shot': 'Quick Shot', 'aimed_shot': 'Aimed Shot',
    'shoot_bolt': 'Shoot Bolt', 'shoot_stake': 'Shoot Heavy Bolt',
    'fire_handgonne_skill': 'Fire Handgonne',
    'throw_javelin': 'Throw Javelin', 'throw_axe': 'Throw Axe',
    'throw_spear': 'Throw Spear', 'throw_balls': 'Throw Bola',
    'sling_stone_skill': 'Sling Stone',
    'pound': 'Pound', 'thresh': 'Thresh',
    'cascade': 'Cascade', 'hail': 'Hail',
    'whip_skill': 'Whip', 'disarm': 'Disarm',
    'knock_over': 'Knock Over', 'strike_down_skill': 'Strike Down',
    'cudgel_skill': 'Cudgel', 'smite_skill': 'Smite', 'shatter': 'Shatter',
    'lunge_skill': 'Lunge', 'prong': 'Prong',
    'crumble': 'Crumble',
    'demolish_armor_skill': 'Demolish Armor',
    'batter_skill': 'Batter (Polehammer)',
    'strike': 'Strike', 'reap': 'Reap',
    'ignite_skill': 'Ignite',
    'flail_skill': 'Flail',
    'lash_skill': 'Lash',
    'cascade_skill': 'Cascade',
    'hail_skill': 'Hail',
    'hammer': 'Batter',
    'shatter_skill': 'Shatter',
    'reap_skill': 'Reap',
    'throw_spear_skill': 'Throw Spear',
    'reload_bolt': '_RELOAD_',
    'reload_handgonne_skill': '_RELOAD_',
    'disarm_skill': 'Disarm',
    'strike_skill': 'Strike',
    'crumble_skill': 'Crumble',
    'knock_over_skill': 'Knock Over',
    'gash_skill': 'Gash',
    'prong_skill': 'Prong',
}

# Map our weapon names to BB source file names (without .nut)
WEAPON_FILE_MAP = {
    'Ancient Bladed Pike': 'ancient_bladed_pike',
    'Ancient Spear': 'ancient_spear',
    'Ancient Sword': 'ancient_sword',
    'Antler Cleaver': 'antler_cleaver',
    'Arming Sword': 'arming_sword',
    'Axehammer': 'axehammer',
    'Bardiche': 'bardiche',
    'Battle Whip': 'battle_whip',
    'Berserk Chain': 'orc_flail_2h',
    'Billhook': 'billhook',
    'Bludgeon': 'bludgeon',
    'Blunt Cleaver': 'blunt_cleaver',
    'Boar Spear': 'boar_spear',
    'Boondock Bow': 'goblin_bow',
    'Broken Ancient Bladed Pike': 'broken_ancient_bladed_pike',
    'Broken Ancient Sword': 'broken_ancient_sword',
    'Bundle of Crude Javelins': 'crude_javelin',
    'Bundle of Heavy Javelins': 'heavy_javelin',
    'Bundle of Heavy Throwing Axes': 'heavy_throwing_axe',
    'Bundle of Javelins': 'javelin',
    'Bundle of Spiked Bolas': 'spiked_balls',
    'Bundle of Throwing Axes': 'throwing_axe',
    "Butcher's Cleaver": 'butchers_cleaver',
    'Claw Club': 'orc_club',
    'Composite Bow': 'composite_bow',
    'Crossbow': 'crossbow',
    'Crude Axe': 'crude_axe',
    'Cruel Falchion': 'falchion_cruel',
    'Crypt Cleaver': 'crypt_cleaver',
    'Cudgel': 'cudgel',
    'Dagger': 'dagger',
    'Falchion': 'falchion',
    'Falx': 'falx',
    'Fencing Sword': 'fencing_sword',
    'Fighting Axe': 'fighting_axe',
    'Fighting Spear': 'fighting_spear',
    'Fire Lance': 'fire_lance',
    'Flail': 'flail',
    'Gnarly Staff': 'goblin_staff',
    'Goblin Notched Blade': 'goblin_notched_blade',
    'Goblin Skewer': 'goblin_spear',
    'Goedendag': 'goedendag',
    'Greataxe': 'greataxe',
    'Greatsword': 'greatsword',
    'Handaxe': 'handaxe',
    'Handgonne': 'handgonne',
    'Hatchet': 'hatchet',
    'Head Chopper': 'head_chopper',
    'Head Splitter': 'head_splitter',
    'Heavy Crossbow': 'heavy_crossbow',
    'Heavy Rusty Axe': 'heavy_rusty_axe',
    'Heavy Southern Mace': 'oriental_mace_heavy',
    'Hooked Blade': 'hooked_blade',
    'Hunting Bow': 'hunting_bow',
    'Jagged Pike': 'jagged_pike',
    'Khopesh': 'khopesh',
    'Knife': 'knife',
    'Light Crossbow': 'light_crossbow',
    'Light Southern Mace': 'oriental_mace_light',
    'Longaxe': 'longaxe',
    'Longsword': 'longsword',
    'Man Splitter': 'orc_axe_2h',
    'Masterwork Bow': 'war_bow_2',
    'Military Cleaver': 'military_cleaver',
    'Military Pick': 'military_pick',
    'Militia Spear': 'militia_spear',
    'Morning Star': 'morning_star',
    'Noble Sword': 'noble_sword',
    'Nomad Mace': 'oriental_mace',
    'Nomad Sling': 'sling',
    'Pickaxe': 'pickaxe',
    'Pike': 'pike',
    'Pitchfork': 'pitchfork',
    'Polehammer': 'polehammer',
    'Polemace': 'polemace',
    'Qatal Dagger': 'qatal_dagger',
    'Reinforced Boondock Bow': 'goblin_bow_2',
    'Reinforced Wooden Flail': 'wooden_flail_2',
    'Rhomphaia': 'rhomphaia',
    'Rondel Dagger': 'rondel_dagger',
    'Rusty Warblade': 'rusty_warblade',
    'Saif': 'oriental_sword',
    'Scimitar': 'scimitar',
    'Scramasax': 'scramasax',
    'Shamshir': 'oriental_sword_shamshir',
    'Short Bow': 'short_bow',
    'Shortsword': 'shortsword',
    'Spetum': 'spetum',
    'Spiked Impaler': 'spiked_impaler',
    'Staff Sling': 'staff_sling',
    'Swordlance': 'swordlance',
    'Thorned Whip': 'thorned_whip',
    'Three-Headed Flail': 'three_headed_flail',
    'Throwing Spear': 'throwing_spear',
    'Tree Limb': 'orc_club_2',
    'Two-Handed Flail': 'two_handed_flail',
    'Two-Handed Flanged Mace': 'two_handed_flanged_mace',
    'Two-Handed Hammer': 'two_handed_hammer',
    'Two-Handed Mace': 'two_handed_mace',
    'Two-Handed Mallet': 'two_handed_mallet',
    'Two-Handed Saif': 'oriental_cleaver_02',
    'Two-Handed Scimitar': 'oriental_cleaver_01',
    'Two-Handed Skull Hammer': 'orc_hammer_2h',
    'Two-Handed Spiked Mace': 'orc_mace_2h',
    'Two-Handed Wooden Flail': 'two_handed_wooden_flail',
    'War Bow': 'war_bow',
    'Warbrand': 'warbrand',
    'Warfork': 'warfork',
    'Warhammer': 'warhammer',
    'Warscythe': 'warscythe',
    'Winged Mace': 'winged_mace',
    'Wonky Bow': 'wonky_bow',
    "Woodcutter's Axe": 'woodcutters_axe',
    'Wooden Flail': 'wooden_flail',
    'Wooden Stick': 'wooden_stick',
}


def find_weapon_file(bb_name):
    """Find the .nut file for a BB weapon, searching subdirectories."""
    for root, dirs, files in os.walk(BB_WEAPONS):
        if 'named' in root:
            continue
        for f in files:
            if f == bb_name + '.nut':
                return os.path.join(root, f)
    return None


def extract_skills(filepath):
    """Extract skill names from a BB weapon .nut file.

    Searches for all scripts/skills/actives/ references, not just
    direct addSkill calls, since many weapons use local variables.
    """
    with open(filepath, 'r') as f:
        content = f.read()
    skills = []
    seen = set()
    for match in re.finditer(
            r'scripts/skills/actives/(\w+)', content):
        script_name = match.group(1)
        if script_name in seen:
            continue
        seen.add(script_name)
        mapped = SKILL_NAME_MAP.get(script_name)
        if mapped and mapped != '_RELOAD_':
            skills.append(mapped)
        elif not mapped:
            skills.append(f'UNKNOWN:{script_name}')
    return skills


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT name, unique_slug, mastery FROM weapon ORDER BY name')
    weapons = cursor.fetchall()

    skill_map = {}
    cursor.execute('''
        SELECT m.weapon_id, ws.name as skill_name
        FROM weapon_skill_map m
        JOIN weapon_skill ws ON ws.internal_id = m.internal_id
            AND ws.is_mastery = 0
        ORDER BY m.weapon_id, m.sort_order
    ''')
    for r in cursor.fetchall():
        skill_map.setdefault(r['weapon_id'], []).append(r['skill_name'])

    cursor.close()
    conn.close()

    checked = 0
    errors = []
    skipped = []

    for w in weapons:
        name = w['name']
        bb_key = WEAPON_FILE_MAP.get(name)
        if not bb_key:
            skipped.append(name)
            continue

        filepath = find_weapon_file(bb_key)
        if not filepath:
            skipped.append(f'{name} (file not found: {bb_key})')
            continue

        checked += 1
        bb_skills = extract_skills(filepath)
        db_skills = skill_map.get(name, [])

        if bb_skills != db_skills:
            errors.append({
                'weapon': name,
                'bb': bb_skills,
                'db': db_skills,
            })

    print(f'Checked: {checked}')
    print(f'Skipped: {len(skipped)}')
    print(f'Errors: {len(errors)}')
    print()

    if errors:
        print('=== MISMATCHES ===')
        for e in errors:
            print(f'{e["weapon"]}')
            print(f'  BB:  {e["bb"]}')
            print(f'  DB:  {e["db"]}')
            print()

    if skipped:
        print(f'=== SKIPPED ({len(skipped)}) ===')
        for s in skipped:
            print(f'  {s}')


if __name__ == '__main__':
    main()
