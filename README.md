# bb-damage

The Battle Brothers damage calculator at **damage.bloodngold.com**. Flask +
MySQL. Reuses the sibling `bb-damage-engine` package for the damage math (its
`nimble_multiplier` is the one Python home for the Nimble formula) and serves
bb-damage-engine's browser JS at `/bb-damage-engine/<path>`.

## Routes

- `/` - the calculator. Query params select weapon / enemy / skill / mods;
  parameterized URLs carry `noindex,follow` and canonical to bare `/`.
- `/spec` - the plain-English damage calculation spec
- `/cache` - simulation result cache view
- `/bb-damage-engine/<path>` - bb-damage-engine's browser JS
- legacy 301s: `/damage-calculator*` and `/calculator` -> `/`

## Database: `bb_damage`

Weapon stats, skill mechanics, and weapon->skill connections are READ FROM the
shared `bb_data` (`item_weapon`, `weapon_skill`, `weapon_skill_connection`) via
cross-database joins (single source of truth, no copy). Only DAMAGE skills
(`bb_data.weapon_skill.damage_perc > 0`) are listed; head/body forcing comes from
`bb_data.weapon_skill.force_body_part`.

`bb_damage` holds only what `bb_data` doesn't carry:

- `weapon` (`id, name, unique_slug`) - the curated calculator weapons + display
  name/slug (`bb_data.item_weapon` has no name).
- `weapon_skill_display` (`name, is_mastery, label, damage_calculator_tooltip,
  show_in_calculator`) - calculator hover text + the curated masteries that
  change the calc's output. `show_in_calculator=0` also excludes Split Shield.
- `enemy`, `enemy_armor_loadout`, `enemy_perk`, `enemy_skill_resistance` (keyed by
  skill slug), `attacker_buff` - no `bb_data` equivalent.
- `cache` - calculator results.

## Local & deploy

```
cd webapp && python app.py                          # http://127.0.0.1:5005/
ssh root@46.225.141.38 "bash /var/www/bb-damage/deploy.sh"
```

gunicorn on `127.0.0.1:8002`. The deploy force-reinstalls `bb-damage-engine` from main
every time, because pip skips an already-installed git dependency while its
version stays `0.1.0`. Repo: github.com/pascalklein87/bb-damage (public).
