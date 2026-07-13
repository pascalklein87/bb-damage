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

Its own DB. Holds `cache` (calculator results) plus a self-contained copy of
the BB reference tables the calculator reads: `weapon`, `weapon_skill`,
`weapon_skill_map`, `enemy`, `enemy_armor_loadout`, `enemy_perk`,
`enemy_skill_resistance`, `attacker_buff`.

TODO: read the reference tables from the shared `bb_data` instead of this copy
(single source of truth), leaving `bb_damage` holding only `cache`.

## Local

    cd webapp && python app.py      # http://127.0.0.1:5002/

## Deploy

    ssh root@46.225.141.38 "bash /var/www/bb-damage/deploy.sh"

gunicorn on `127.0.0.1:8002`. The deploy force-reinstalls `bb-engine` from main
every time, because pip skips an already-installed git dependency while its
version stays `0.1.0` (this caused the 2026-07-13 outage).
Repo: github.com/pascalklein87/bb-damage (public).
