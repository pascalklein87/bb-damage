# bb-damage

The Battle Brothers damage calculator at **damage.bloodngold.com**. Flask +
MySQL. Reuses the sibling `bb-damage-engine` package for the damage math (its
`nimble_multiplier` is the one Python home for the Nimble formula) and serves
bb-damage-engine's browser JS at `/bb-damage-engine/<path>`.

## Routes

- `/` - the calculator. Query params select weapon / enemy / skill / mods;
  parameterized URLs carry `noindex,follow` and canonical to bare `/`.
  `init` = the attacker's Initiative, read only for Initiative-scaled skills:
  Lunge multiplies total damage by min(2.0, 2.0 x Initiative / 175)
  (lunge_skill.nut:260), Skewer adds min(0.55, 0.55 x Initiative / 175)
  armor-ignoring damage (skewer_skill.nut:83-84); the field is prefilled with
  88, the nearest integer to Lunge's x1.0 point. `staggered=1` = Assault's
  checkbox: the axe-head Strike follows the Impale (assault_skill.nut:113-118,
  :163-165). Perforate needs no input: the simulator tracks the injuries it
  inflicts and adds one thrust per injury the target carries
  (perforate_skill.nut:79-104).
- `/spec` - the plain-English damage calculation spec
- `/cache` - simulation result cache view
- `/bb-damage-engine/<path>` - bb-damage-engine's browser JS
- legacy 301s: `/damage-calculator*` and `/calculator` -> `/`

## Database: `bb_damage`

Weapon stats, skill mechanics, and weapon->skill connections are READ FROM the
shared `bb_data` (`item_weapon`, `weapon_skill`, `weapon_skill_connection`) via
cross-database joins (single source of truth, no copy). Only DAMAGE skills
(`bb_data.weapon_skill.damage_perc > 0`) are listed; head/body forcing comes from
`bb_data.weapon_skill.force_body_part`. Injuries roll per hit from
`bb_data.injury` (the skill's `injury_category` x the body part hit, each
injury's own threshold, actor.nut:1679-1704); a stance like Riposte injures
with the weapon's default attack, a skill without a list (Destroy Armor) never.

`bb_damage` holds only what `bb_data` doesn't carry:

- `weapon` (`id, name, unique_slug`) - the curated calculator weapons + display
  name/slug (`bb_data.item_weapon` has no name). Every regular buyable weapon is
  in; Lute, the three legendaries, and the Named / Battle Standard design rows
  stay out (Named stats are entered via the editable weapon stats).
- `weapon_skill_display` (`name, is_mastery, label, damage_calculator_tooltip,
  show_in_calculator`) - calculator hover text + the curated masteries that
  change the calc's output. `show_in_calculator=0` also excludes Split Shield.
- `enemy`, `enemy_armor_loadout`, `enemy_perk`, `enemy_skill_resistance` (keyed by
  skill slug), `attacker_buff` - no `bb_data` equivalent.
- `cache` - calculator results.

## Deviations from BB

Every deliberate difference from Battle Brothers is in `docs/deviations.txt`; only
the user adds entries there (a found gap goes to `todos.md`).

## Local & deploy

```
cd webapp && python app.py                          # http://127.0.0.1:5005/
ssh root@46.225.141.38 "bash /var/www/bb-damage/deploy.sh"
```

gunicorn on `127.0.0.1:8002`. The deploy force-reinstalls `bb-damage-engine` from main
every time, because pip skips an already-installed git dependency while its
version stays `0.1.0`. Repo: github.com/pascalklein87/bb-damage (public).
