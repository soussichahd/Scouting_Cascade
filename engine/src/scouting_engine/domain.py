"""Domaine : fonctions d'appartenance, variables, règles. Aucun nom de variable en dur."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np


def trapmf(x, p):
    """Appartenance trapézoïdale [a,b,c,d] ; triangle [a,b,c] = [a,b,b,c].
    Épaulements gérés (a==b : plateau dès a ; c==d : plateau jusqu'à d)."""
    if len(p) == 3:
        p = [p[0], p[1], p[1], p[2]]
    a, b, c, d = map(float, p)
    x = np.asarray(x, dtype=float)
    up = (x - a) / (b - a) if b > a else np.where(x >= a, 1.0, 0.0)
    dn = (d - x) / (d - c) if d > c else np.where(x <= d, 1.0, 0.0)
    return np.clip(np.minimum(up, dn), 0.0, 1.0)


@dataclass
class Term:
    id: str
    label: str
    shape: str
    params: list

    def mu(self, x):
        return trapmf(x, self.params)


@dataclass
class Variable:
    id: str
    label: str
    range: tuple
    terms: list
    unit: str = ""
    inverted: bool = False
    kind: str = "input"
    source: str | None = None  # lit la valeur brute d'une autre entrée (variable partagée)

    @property
    def raw_id(self):
        return self.source or self.id

    def term(self, tid) -> Term:
        for t in self.terms:
            if t.id == tid:
                return t
        raise KeyError(f"Terme inconnu « {tid} » pour la variable {self.id}")

    def term_index(self, tid) -> int:
        return [t.id for t in self.terms].index(tid)

    def fuzzify(self, x) -> dict:
        return {t.id: float(t.mu(x)) for t in self.terms}

    def check(self, x):
        lo, hi = self.range
        if x is None or not (lo - 1e-9 <= float(x) <= hi + 1e-9):
            raise ValueError(f"Valeur hors plage pour « {self.label} » : {x} (plage {lo} à {hi} {self.unit})")

    def default_rank(self, tid) -> float:
        n = len(self.terms)
        r = self.term_index(tid) / (n - 1) if n > 1 else 1.0
        return 1.0 - r if self.inverted else r


def variable_from_dict(d: dict) -> Variable:
    terms = [Term(t["id"], t.get("label", t["id"]), t["shape"], list(t["params"])) for t in d["terms"]]
    return Variable(d["id"], d.get("label", d["id"]), tuple(d["range"]), terms, d.get("unit", ""),
                    bool(d.get("inverted", False)), d.get("kind", "input"), d.get("source"))


def variable_to_dict(v: Variable) -> dict:
    d = {"id": v.id, "label": v.label, "unit": v.unit, "range": list(v.range), "kind": v.kind,
         "terms": [{"id": t.id, "label": t.label, "shape": t.shape, "params": t.params} for t in v.terms]}
    if v.inverted:
        d["inverted"] = True
    if v.source:
        d["source"] = v.source
    return d


@dataclass
class RuleBase:
    id: str
    inputs: list
    output: str
    rules: list          # [{id, if:{var:term}, then:{outvar:term}, weight, author}]
    version: int = 1
    gen: dict = field(default_factory=dict)  # {weights:{var:w}, ranks:{var:{term:r}}}

    def to_dict(self):
        return {"rule_base": self.id, "version": self.version, "gen": self.gen, "rules": self.rules}
