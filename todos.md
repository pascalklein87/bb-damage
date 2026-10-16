# bb-damage todos

Open work only. A finished item is deleted.

- bb-weapons rankings lack Executioner's Sword, Estoc and Pollaxe (its own
  `weapon` copy, 5082 precomputed rows): recompute.
- Dev port collision: the root README gives 5005 to both bb-damage and
  bb-seeds. Decide which moves (recommendation: bb-damage to 5006 in app.py,
  this README and the root README).
- `bb_data.injury` keeps one category per injury, but BB lists some head
  injuries in several pools (Ripped Ear is cutting AND piercing): blunt head
  BB 4 vs 3 rows, cutting head 6 vs 4, piercing head 5 vs 4; body pools
  match. The calculator and bng-game both roll head injuries from the
  smaller pools. Producer fix: a pool junction table in bb_data (schema
  change, needs approval).
- `enemy_armor_loadout` has no `id` primary key (root README: PK is always
  `id`; every SELECT includes it). Schema change, needs approval.
- Nimble for vanilla enemies is a per-enemy average hardcoded in routes.py
  `NIMBLE_MULT` (Gladiator 0.49, Nomad Leader 0.55). BB computes it per worn
  armor (perk_nimble.nut:60-70). Needs a fatigue column on
  `enemy_armor_loadout` (schema change, approval) plus the fatigue of the 19
  loadout rows of the 5 Nimble enemies, then the simulator calls
  `nimble_multiplier` per sampled body+helmet pair and `NIMBLE_MULT` goes.
- Cross-check all enemy rows against their .nut files (perks, heal_per_turn,
  immunities, armor_damage_received_perc, is_headshot_immune). 4 of ~70
  checked on 2026-10-16; the Ifrit headshot immunity was missing.
- Barbarian Madman `racial_trait` 'Regeneration' is hand-written; BB's
  trickster_god_racial.nut has an empty Name. Decide the label source.
- No test asserts that each calculator input moves the result; deploy.sh does
  not clear the cache although the page says it does. Both proposed
  2026-10-16, no GO yet.
- Comments attributing decisions to the user, unverified: routes.py
  `INITIATIVE_DEFAULT` "(user decision 2026-10-11)"; engine attack.py:35 and
  calculator.py:18 "(user rule 2026-06-15)"; engine docs/decisions.md.
