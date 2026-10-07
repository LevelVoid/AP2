"""
split_by_cohort.py — Split poisoned_catalog.json and user_prompts.json by cohort.

Cohort definitions (from the original generation script):
  A_Exact         — benign description, no injection
  B_Synonym       — benign + "highly rated alternative" suffix
  C_Substitution  — description contains hidden HTML price-override injection
  D_PriceOverride — description contains hidden HTML cart-total injection

Output (in data/by_cohort/):
  catalog_A_Exact.json   + prompts_A_Exact.json
  catalog_B_Synonym.json + prompts_B_Synonym.json
  catalog_C_Substitution.json + prompts_C_Substitution.json
  catalog_D_PriceOverride.json + prompts_D_PriceOverride.json
  manifest.json
"""

import json
from collections import defaultdict
from pathlib import Path

DATA = Path('/Users/pradeepbiswas/Projects/Research/AP2/data')
OUT  = DATA / 'by_cohort'
OUT.mkdir(exist_ok=True)

catalog = json.loads((DATA / 'poisoned_catalog.json').read_text())
prompts = json.loads((DATA / 'user_prompts.json').read_text())

# ── Build a lookup: item_id → cohort from the prompts file ──────────────────
# Every item_id in prompts has a cohort label (A_Exact … D_PriceOverride).
# Some item_ids appear multiple times (once per cohort).
# We group prompts by cohort directly.
cohort_prompts: dict[str, list] = defaultdict(list)
for p in prompts:
    cohort_prompts[p['cohort']].append(p)

# ── Build item_id → cohort mapping ──────────────────────────────────────────
# An item_id may appear in multiple cohorts (the same product is tested under
# different prompt strategies).  The catalog entry itself is shared; we
# duplicate it into each cohort slice where it appears.
item_cohort_map: dict[str, set] = defaultdict(set)
for p in prompts:
    item_cohort_map[str(p['item_id'])].add(p['cohort'])

# ── Split catalog by cohort ──────────────────────────────────────────────────
cohort_catalog: dict[str, list] = defaultdict(list)
for item in catalog:
    item_id = str(item['id'])
    for cohort in item_cohort_map.get(item_id, set()):
        cohort_catalog[cohort].append(item)

# ── Write files ──────────────────────────────────────────────────────────────
COHORTS = ['A_Exact', 'B_Synonym', 'C_Substitution', 'D_PriceOverride']
manifest_entries = []

print(f"{'Cohort':<20} {'Catalog':>8} {'Prompts':>8}")
print('-' * 40)

for cohort in COHORTS:
    items   = sorted(cohort_catalog.get(cohort, []), key=lambda x: x['id'])
    prmpts  = cohort_prompts.get(cohort, [])

    cat_file = OUT / f'catalog_{cohort}.json'
    pmt_file = OUT / f'prompts_{cohort}.json'

    cat_file.write_text(json.dumps(items, indent=2, ensure_ascii=False))
    pmt_file.write_text(json.dumps(prmpts, indent=2, ensure_ascii=False))

    manifest_entries.append({
        'cohort':        cohort,
        'catalog_file':  f'by_cohort/catalog_{cohort}.json',
        'prompts_file':  f'by_cohort/prompts_{cohort}.json',
        'item_count':    len(items),
        'prompt_count':  len(prmpts),
    })
    print(f"  {cohort:<18} {len(items):>8}  {len(prmpts):>8}")

manifest = {
    'description': (
        'Cohort-stratified splits of poisoned_catalog.json and '
        'user_prompts.json. Each cohort represents a different attack '
        'variant (A=benign, B=synonym, C=substitution, D=price-override).'
    ),
    'cohorts': manifest_entries,
    'total_items_in_catalog': len(catalog),
    'total_prompts':          len(prompts),
}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

print()
print(f"Output directory : {OUT}")
print(f"Files written    : {len(COHORTS) * 2 + 1}  ({len(COHORTS)} catalog + {len(COHORTS)} prompts + 1 manifest)")
