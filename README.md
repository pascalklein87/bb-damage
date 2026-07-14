# bb-damage

The Battle Brothers damage calculator at **damage.bloodngold.com**. Flask +
MySQL. Reuses the sibling `bb-engine` package for the damage math (its
`nimble_multiplier` is the one Python home for the Nimble formula) and serves
bb-engine's browser JS at `/bb-engine/<path>`.

Split out of the old `bb-wiki` monolith on 2026-07-13.

## Routes

- `/` - the calculator. Query params select weapon / enemy / skill / mods;
  parameterized URLs carry `noindex,follow` and canonical to the bare `/`.
- `/spec` - the plain-English damage calculation spec
- `/cache` - simulation result cache view
- `/bb-engine/<path>` - bb-engine's browser JS
- legacy 301s: `/damage-calculator*` and `/calculator` -> `/`

## Database: `bb_damage`

Weapon stats, skill mechanics, and weapon->skill connections are READ FROM the
shared `bb_data` (`item_weapon`, `weapon_skill`, `weapon_skill_connection`) via
cross-database joins - single source of truth, no copy. Only DAMAGE skills
(`bb_data.weapon_skill.damage_perc > 0`) are listed; head/body forcing comes
from `bb_data.weapon_skill.force_body_part` (Puncture -> body, Lash/Hail -> head).

`bb_damage` holds only what `bb_data` does not carry:

- `weapon` (`id, name, unique_slug`) - the curated calculator weapons plus their
  display name/slug (`bb_data.item_weapon` has no name).
- `weapon_skill_display` (`name, is_mastery, label, damage_calculator_tooltip,
  show_in_calculator`) - calculator hover text, plus the curated set of
  masteries that change the calc's output (a mastery shows only when flagged;
  the flag is the old wiki curation, verified against bb_data's damage columns).
  `show_in_calculator=0` also excludes Split Shield (damages shields, not the enemy).
- `enemy`, `enemy_armor_loadout`, `enemy_perk`, `enemy_skill_resistance`
  (keyed by skill slug), `attacker_buff` - no `bb_data` equivalent.
- `cache` - calculator results.

## Local

    cd webapp && python app.py      # http://127.0.0.1:5002/

## Deploy

    ssh root@46.225.141.38 "bash /var/www/bb-damage/deploy.sh"

gunicorn on `127.0.0.1:8002`. The deploy force-reinstalls `bb-engine` from main
every time, because pip skips an already-installed git dependency while its
version stays `0.1.0` (this caused the 2026-07-13 outage).
Repo: github.com/pascalklein87/bb-damage (public).
