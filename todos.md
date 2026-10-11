# bb-damage todos

Open work only. A finished item is deleted.

- bb-weapons rankings lack Executioner's Sword, Estoc and Pollaxe (its own
  `weapon` copy, 5082 precomputed rows): recompute.
- Dev port collision: the root README gives 5005 to both bb-damage and
  bb-seeds. Decide which moves (recommendation: bb-damage to 5006 in app.py,
  this README and the root README).
- `/spec` page has no paragraphs for the Initiative scaling (Lunge, Skewer),
  Execute's head chance, Perforate's thrust count or Assault's Strike.
- Racial resistance misses the throwing mastery variants: their slugs
  (`throw-axe3t`, `throw-axe2t`, ...) are not the `enemy_skill_resistance`
  keys (`throw-axe`), so Serpent / Schrat rows do not apply to them. Key the
  lookup by the base skill slug.
