"""Validation des variables (sommets, couverture, recouvrement) et des bases de règles (complétude, conflits)."""
import itertools
import numpy as np


def validate_variable(v) -> dict:
    errors, warnings = [], []
    lo, hi = v.range
    for t in v.terms:
        p = t.params
        if any(p[i] > p[i + 1] for i in range(len(p) - 1)):
            errors.append(f"{t.label} : sommets non ordonnés {p}")
        if min(p) < lo - 1e-9 or max(p) > hi + 1e-9:
            errors.append(f"{t.label} : sommets hors de la plage {lo}–{hi}")
    if not errors:
        xs = np.linspace(lo, hi, 2001)
        cov = np.max([t.mu(xs) for t in v.terms], axis=0)
        if cov.min() <= 0:
            warnings.append(f"Trou de couverture autour de {xs[np.argmin(cov)]:.3g}")
        order = sorted(v.terms, key=lambda t: sum(t.params) / len(t.params))
        for a, b in zip(order, order[1:]):
            if not np.any((a.mu(xs) > 0) & (b.mu(xs) > 0)):
                warnings.append(f"Perte d'incertitude : {a.label} et {b.label} ne se recouvrent pas")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def check_rulebase(rb, variables) -> dict:
    in_vars = [variables[i] for i in rb.inputs]
    total = 1
    for v in in_vars:
        total *= len(v.terms)
    seen, conflicts = {}, []
    for r in rb.rules:
        key = tuple(r["if"].get(v.id) for v in in_vars)
        out = tuple(r["then"].values())
        if key in seen and seen[key][1] != out:
            conflicts.append({"premise": r["if"], "rules": [seen[key][0], r["id"]]})
        seen.setdefault(key, (r["id"], out))
    covered = 0
    missing = []
    for combo in itertools.product(*[[t.id for t in v.terms] for v in in_vars]):
        hit = any(all(k is None or k == c for k, c in zip(key, combo)) for key in seen)
        covered += hit
        if not hit and len(missing) < 50:
            missing.append(dict(zip(rb.inputs, combo)))
    return {"total_combinations": total, "covered": covered, "coverage": covered / total if total else 1.0,
            "missing": missing, "conflicts": conflicts}
