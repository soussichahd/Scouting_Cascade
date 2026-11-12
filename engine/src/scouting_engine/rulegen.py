"""Génération pondérée d'une base complète : score ordinal pondéré -> terme de sortie le plus proche."""
import itertools, math


def generate_rules(rb_id, in_vars, out_var, gen, author="generator"):
    w = gen.get("weights", {})
    ranks = gen.get("ranks", {})
    wsum = sum(w.get(v.id, 1.0) for v in in_vars) or 1.0
    n_out = len(out_var.terms)
    rules = []
    for k, combo in enumerate(itertools.product(*[[t.id for t in v.terms] for v in in_vars]), 1):
        s = 0.0
        for v, t in zip(in_vars, combo):
            r = ranks.get(v.id, {}).get(t, v.default_rank(t))
            s += w.get(v.id, 1.0) * r
        s /= wsum
        idx = min(n_out - 1, max(0, math.floor(s * (n_out - 1) + 0.5 + 1e-9)))
        rules.append({"id": f"{rb_id}-{k:03d}", "if": {v.id: t for v, t in zip(in_vars, combo)},
                      "then": {out_var.id: out_var.terms[idx].id}, "weight": 1.0, "author": author})
    return rules
