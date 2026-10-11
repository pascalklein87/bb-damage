# bb-damage todos

Open work only. A finished item is deleted.

- Patch 1.5.2.2 weapons missing from the calculator: Executioner's Sword
  (bb_data 265), Estoc (268), Pollaxe (271). Needs `bb_damage.weapon` rows,
  `weapon_skill_display` rows for Execute / Skewer / Perforate / Assault,
  `enemy_skill_resistance` rows `perforate` + `skewer` x0.5 for the enemies that
  carry `stab` x0.5 (skeleton_racial.nut:38-39, alp_racial.nut:52-53,
  golem_racial.nut:95-96), and these skill mechanics:
  - Execute: +15 head-hit chance (execute_skill.nut:116).
  - Skewer: +20 flat damage (skewer_skill.nut:85-86, store as
    bb_data.weapon_skill.damage_bonus like Smite / Pound) and armor-ignore
    +min(0.55, 0.55 x Initiative / 175) (skewer_skill.nut:83-84) via the
    existing `init` input.
  - Perforate as two entries: plain = 2 thrusts, injured target = 3 thrusts
    (perforate_skill.nut:79, 128); full-damage independent rolls.
  - Assault as two entries: plain = Impale only; staggered target = Impale +
    Strike at x0.75 total, x1.2 armor, +0.2 piercing (assault_skill.nut:163-165).
- bb-weapons rankings lack the same three weapons (its own `weapon` copy, 5082
  precomputed rows): recompute after they land here.
- Dev port collision: the root README gives 5005 to both bb-damage and
  bb-seeds. Decide which moves (recommendation: bb-damage to 5006 in app.py,
  this README and the root README).
- `/spec` page has no paragraph for the Initiative scaling yet.
