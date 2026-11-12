"""Algorithme génétique : calibre les poids de génération des bases (cascade) pour minimiser l'EQM vs notes d'experts."""
import numpy as np
from .model import Model
from .rulegen import generate_rules
from .domain import RuleBase

def _genes(model):
    genes = []
    for n in model.cascade["nodes"]:
        for i in n["inputs"]:
            genes.append((n["rulebase"], i))
    return genes

def build_with_weights(model, genes, vec, n_points=None):
    rbs = {k: RuleBase(r.id, r.inputs, r.output, r.rules, r.version, {**r.gen, "weights": dict(r.gen.get("weights", {}))})
           for k, r in model.rulebases.items()}
    for (rb, var), w in zip(genes, vec):
        rbs[rb].gen["weights"][var] = float(w)
    for n in model.cascade["nodes"]:
        rb = rbs[n["rulebase"]]
        rb.rules = generate_rules(rb.id, [model.variables[i] for i in n["inputs"]], model.variables[n["output"]], rb.gen)
    return model.clone(rulebases=rbs, n_points=n_points or model.n_points)

def mse(m, rows, y):
    return float(np.mean([(m.score(r) - t) ** 2 for r, t in zip(rows, y)]))

def optimize(model, rows, y, seed=42, pop=16, gens=12, val_frac=0.3, n_points=120):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(rows)); nv = int(len(rows) * val_frac)
    va, tr = idx[:nv], idx[nv:]
    Xtr, ytr = [rows[i] for i in tr], [y[i] for i in tr]
    Xva, yva = [rows[i] for i in va], [y[i] for i in va]
    genes = _genes(model)
    x0 = np.array([model.rulebases[rb].gen.get("weights", {}).get(v, 1.0) for rb, v in genes])
    fit = lambda g: mse(build_with_weights(model, genes, g, n_points), Xtr, ytr)
    P = [x0] + [np.clip(x0 * rng.uniform(0.4, 1.8, len(x0)), 0.02, 1.0) for _ in range(pop - 1)]
    F = [fit(p) for p in P]; history = [min(F)]
    for _ in range(gens):
        order = np.argsort(F); P = [P[i] for i in order]; F = [F[i] for i in order]
        new = P[:2]; nf = F[:2]                                 # élitisme
        while len(new) < pop:
            a, b = (P[min(rng.integers(0, pop, 2))], P[min(rng.integers(0, pop, 2))])
            mask = rng.random(len(x0)) < 0.5
            child = np.where(mask, a, b) * np.where(rng.random(len(x0)) < 0.2, rng.uniform(0.7, 1.3, len(x0)), 1.0)
            child = np.clip(child, 0.02, 1.0); new.append(child); nf.append(fit(child))
        P, F = new, nf; history.append(min(F))
    best = P[int(np.argmin(F))]
    def full(g, X, Y): return mse(build_with_weights(model, genes, g), X, Y)
    return {"genes": [f"{rb}:{v}" for rb, v in genes], "best": best.tolist(), "seed": seed,
            "params": {"pop": pop, "gens": gens, "val_frac": val_frac, "fit_points": n_points},
            "train_mse_before": full(x0, Xtr, ytr), "train_mse_after": full(best, Xtr, ytr),
            "val_mse_before": full(x0, Xva, yva), "val_mse_after": full(best, Xva, yva),
            "history": history, "model": build_with_weights(model, genes, best)}
