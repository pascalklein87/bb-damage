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
