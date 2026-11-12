"""Fuzzy C-Means, normalisation 0-1, similarité."""
import numpy as np

def normalize(model, row: dict, ids):
    out = []
    for i in ids:
        v = model.variables[i]; lo, hi = v.range
        x = (float(row[v.raw_id]) - lo) / (hi - lo)
        out.append(1 - x if v.inverted else x)   # 1 = favorable pour toutes les variables
    return np.array(out)

def fcm(X, c=3, m=2.0, iters=300, tol=1e-6, seed=42):
    rng = np.random.default_rng(seed)
    n = len(X)
    U = rng.random((c, n)); U /= U.sum(axis=0)
    for _ in range(iters):
        Um = U ** m
        C = Um @ X / Um.sum(axis=1, keepdims=True)
        D = np.linalg.norm(X[None, :, :] - C[:, None, :], axis=2) + 1e-12
        Un = 1.0 / (D ** (2 / (m - 1)) * np.sum(D ** (-2 / (m - 1)), axis=0))
        if np.abs(Un - U).max() < tol:
            U = Un; break
        U = Un
    fpc = float((U ** 2).sum() / n)   # coefficient de partition (1 = partition nette)
    order = np.argsort(-C.mean(axis=1))
    return C[order], U[order], fpc

def auto_names(C, ids, labels):
    names = []
    for k, c in enumerate(C):
        top = ids[int(np.argmax(c))]; low = ids[int(np.argmin(c))]
        names.append(f"Profil {k+1} · fort en {labels[top].lower()}, moyen en {labels[low].lower()}")
    return names

def similar(model, target: dict, pool: list, metric="cosine", space="variables", k=5):
    ids = ([i for i in model.required_inputs() if i in model.variables and model.variables[i].kind == "input"
            and i not in ("age", "minutes_played", "league_visibility")] if space == "variables" else None)
    def vec(row):
        if space == "variables":
            return normalize(model, row, ids)
        res = model.evaluate(row, with_trace=False)
        return np.array([s["value"] / 10 for s in res["subscores"].values()])
    t = vec(target); out = []
    for g in pool:
        v = vec(g)
        d = (1 - float(t @ v / (np.linalg.norm(t) * np.linalg.norm(v)))) if metric == "cosine" else float(np.linalg.norm(t - v))
        out.append({"id": g.get("id"), "name": g.get("name"), "distance": max(0.0, d)})
    return sorted(out, key=lambda r: r["distance"])[:k]
