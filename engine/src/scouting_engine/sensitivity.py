"""Analyse « et si » : rejoue l'évaluation avec une variation d'une variable."""
def _fired(res):
    return {(nid, r["id"]) for nid, t in res["trace"].items() if t for r in t["fired_rules"]}

def sensitivity(model, inputs, variable, delta, mode="absolute"):
    v = model.variables[variable]
    base = model.evaluate_full(inputs)
    new = dict(inputs)
    x = inputs[variable]
    x2 = x + delta if mode == "absolute" else x * (1 + delta / 100.0)
    new[variable] = min(max(x2, v.range[0]), v.range[1])
    r2 = model.evaluate_full(new)
    a, b = _fired(base), _fired(r2)
    return {"variable": variable, "old_value": x, "new_value": new[variable],
            "old_score": base["final"]["score"], "new_score": r2["final"]["score"],
            "delta_score": r2["final"]["score"] - base["final"]["score"],
            "old_level": base["final"]["level_label"], "new_level": r2["final"]["level_label"],
            "rules_added": sorted(f"{n}:{i}" for n, i in b - a), "rules_removed": sorted(f"{n}:{i}" for n, i in a - b)}
