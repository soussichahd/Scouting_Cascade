"""Moteur Mamdani générique + cascade lue depuis cascade.yaml (graphe de nœuds)."""
from __future__ import annotations
import copy
from pathlib import Path
import numpy as np
import yaml
from .domain import Variable, RuleBase, variable_from_dict, variable_to_dict
from .rulegen import generate_rules


class NoRuleFiredError(RuntimeError):
    """Aucune règle activée : l'aire agrégée est nulle, le moteur refuse de renvoyer 0."""


class CompiledNode:
    def __init__(self, spec, variables, rb: RuleBase, n_points):
        self.id, self.spec, self.rb = spec["id"], spec, rb
        self.in_vars = [variables[i] for i in spec["inputs"]]
        self.out_var = variables[spec["output"]]
        self.z = np.linspace(self.out_var.range[0], self.out_var.range[1], n_points)
        self.out_mu = np.array([t.mu(self.z) for t in self.out_var.terms])
        n = len(self.in_vars)
        self.idx = np.full((len(rb.rules), n), -1, dtype=int)
        self.out_idx = np.zeros(len(rb.rules), dtype=int)
        self.w = np.ones(len(rb.rules))
        for k, r in enumerate(rb.rules):
            for j, v in enumerate(self.in_vars):
                if v.id in r["if"]:
                    self.idx[k, j] = v.term_index(r["if"][v.id])
            self.out_idx[k] = self.out_var.term_index(r["then"][self.out_var.id])
            self.w[k] = float(r.get("weight", 1.0))

    def run(self, values, with_trace=True):
        degrees = []
        for v in self.in_vars:
            x = values[v.raw_id]
            v.check(x)
            degrees.append(np.array([float(t.mu(x)) for t in v.terms]))
        if len(self.idx):
            cols = []
            for j, d in enumerate(degrees):
                ij = self.idx[:, j]
                cols.append(np.where(ij >= 0, d[np.maximum(ij, 0)], 1.0))
            strength = np.min(cols, axis=0) * self.w
            # une règle sans aucune prémisse ne doit pas s'activer
            strength = np.where((self.idx >= 0).any(axis=1), strength, 0.0)
        else:
            strength = np.zeros(0)
        n_t = len(self.out_var.terms)
        S = np.zeros(n_t)
        for t in range(n_t):
            m = self.out_idx == t
            if m.any():
                S[t] = strength[m].max()
        agg = np.max(np.minimum(S[:, None], self.out_mu), axis=0)
        area = agg.sum()
        if area <= 0:
            raise NoRuleFiredError(f"Aucune règle activée pour le système « {self.id} » (entrées : "
                                   f"{ {v.id: values[v.raw_id] for v in self.in_vars} }).")
        out = float((self.z * agg).sum() / area)
        res = {"value": out, "term_strengths": {t.id: float(s) for t, s in zip(self.out_var.terms, S)}}
        if with_trace:
            fired = [{"id": self.rb.rules[k]["id"], "if": self.rb.rules[k]["if"], "then": self.rb.rules[k]["then"],
                      "strength": float(strength[k])} for k in np.argsort(-strength) if strength[k] > 0]
            step = max(1, len(self.z) // 200)
            res["trace"] = {"degrees": {v.id: {t.id: float(d[i]) for i, t in enumerate(v.terms)}
                                        for v, d in zip(self.in_vars, degrees)},
                            "fired_rules": fired, "z": self.z[::step].tolist(), "aggregated": agg[::step].tolist(),
                            "centroid": out}
        return res


class Model:
    def __init__(self, variables: dict, cascade: dict, rulebases: dict, n_points=1000):
        self.variables, self.cascade, self.rulebases, self.n_points = variables, cascade, rulebases, n_points
        self.node_specs = cascade["nodes"] + cascade.get("parallel", [])
        self.settings = cascade.get("settings", {})
        self.order = self._topo(cascade["nodes"])
        self.nodes = {s["id"]: CompiledNode(s, variables, rulebases[s["rulebase"]], n_points) for s in self.node_specs}

    @staticmethod
    def _topo(nodes):
        outs = {n["output"]: n for n in nodes}
        done, order = set(), []
        def visit(n, stack=()):
            if n["id"] in done:
                return
            if n["id"] in stack:
                raise ValueError("Cycle dans cascade.yaml")
            for i in n["inputs"]:
                if i in outs:
                    visit(outs[i], stack + (n["id"],))
            done.add(n["id"]); order.append(n["id"])
        for n in nodes:
            visit(n)
        return order

    # ---------- chargement ----------
    @classmethod
    def from_dir(cls, d, n_points=1000):
        d = Path(d)
        vs = yaml.safe_load((d / "variables.yaml").read_text(encoding="utf-8"))
        variables = {x["id"]: variable_from_dict(x) for x in vs["variables"]}
        cascade = yaml.safe_load((d / "cascade.yaml").read_text(encoding="utf-8"))
        rbs = {}
        for f in sorted((d / "rulebases").glob("*.yaml")):
            y = yaml.safe_load(f.read_text(encoding="utf-8"))
            node = next(s for s in cascade["nodes"] + cascade.get("parallel", []) if s["rulebase"] == y["rule_base"])
            rbs[y["rule_base"]] = RuleBase(y["rule_base"], node["inputs"], node["output"], y["rules"],
                                           y.get("version", 1), y.get("gen", {}))
        return cls(variables, cascade, rbs, n_points)

    def clone(self, variables=None, rulebases=None, n_points=None):
        return Model(variables or self.variables, self.cascade, rulebases or self.rulebases, n_points or self.n_points)

    # ---------- évaluation ----------
    def required_inputs(self):
        outs = {s["output"] for s in self.node_specs}
        need = []
        for s in self.node_specs:
            for i in s["inputs"]:
                if i not in outs and self.variables[i].raw_id not in need:
                    need.append(self.variables[i].raw_id)
        return need

    def evaluate(self, inputs: dict, with_trace=True) -> dict:
        values = dict(inputs)
        trace, subs = {}, {}
        final_id = self.cascade["final"]
        for nid in self.order:
            node = self.nodes[nid]
            r = node.run(values, with_trace)
            values[node.out_var.id] = r["value"]
            trace[nid] = r.get("trace")
            if nid != final_id:
                subs[node.out_var.id] = {"node": nid, "value": r["value"], "degrees": r["term_strengths"],
                                         "degrees_fuzzy": self.variables[node.out_var.id].fuzzify(r["value"])}
        fnode = self.nodes[final_id]
        score = values[fnode.out_var.id]
        deg = fnode.out_var.fuzzify(score)
        best = max(fnode.out_var.terms, key=lambda t: deg[t.id])
        res = {"subscores": subs, "final": {"score": score, "level": fnode.out_var.term_index(best.id) + 1,
               "level_id": best.id, "level_label": best.label, "degrees": deg,
               "top_rules": [x["id"] for x in (trace[final_id] or {}).get("fired_rules", [])[:5]]}, "trace": trace}
        for par in self.cascade.get("parallel", []):
            pr = self.nodes[par["id"]].run(values, with_trace)
            res[par["id"]] = {"value": pr["value"], "degrees": self.nodes[par["id"]].out_var.fuzzify(pr["value"])}
            res["trace"][par["id"]] = pr.get("trace")
        return res

    def evaluate_full(self, inputs):
        """Évaluation + fiabilité + marge + potentiel (clés stables pour l'API)."""
        r = self.evaluate(inputs)
        rel = r.pop("reliability", None)
        pot = r.pop("potential", None)
        mm = self.settings.get("max_margin", 15.0)
        if rel:
            idx = rel["value"]
            r["reliability"] = {"index": idx, "margin": mm * (1 - idx), "degrees": rel["degrees"]}
        s = r["final"]["score"]
        r["age_potential"] = {"immediate": s, "potential": pot["value"] if pot else None}
        return r

    def score(self, inputs):
        return self.evaluate(inputs, with_trace=False)["final"]["score"]
