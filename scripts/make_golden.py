"""Valeurs d'or : calculées par une implémentation de référence INDÉPENDANTE (boucles pures) – à compléter par des calculs à la main de l'expert."""
import sys, json, random
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT / "engine/src"), str(ROOT / "tests")]
from scouting_engine import Model
from test_engine import naive_node, BASE
random.seed(5)
def naive_full(m, vals):
    vals = dict(vals)
    for nid in m.order:
        n = m.nodes[nid]; vals[n.out_var.id] = naive_node(n, vals)
    return vals[m.nodes[m.cascade["final"]].out_var.id]
for name, d, fixed in (("lateral", "lateral", {}), ("goalkeeper", "goalkeeper", {k: BASE[k] for k in ("age", "minutes_played", "league_visibility")})):
    m = Model.from_dir(ROOT / "data/seed" / d); out = []
    for i in range(12):
        inp = dict(fixed)
        for k in m.required_inputs():
            if k not in fixed:
                lo, hi = m.variables[k].range; inp[k] = round(lo + random.random() * (hi - lo), 3)
        out.append({"name": f"{name}-{i+1}", "inputs": inp, "expected": round(naive_full(m, inp), 4)})
    (ROOT / "data/fixtures/golden" / f"{name}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print("golden OK")
