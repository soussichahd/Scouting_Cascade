import json, itertools, math, pathlib
import numpy as np, pytest
from hypothesis import given, settings, strategies as st
from scouting_engine import Model, NoRuleFiredError, trapmf
from scouting_engine.rulegen import generate_rules
from scouting_engine.validation import validate_variable, check_rulebase
ROOT = pathlib.Path(__file__).resolve().parents[1]

# ---------- fonctions d'appartenance ----------
def test_membership_vertices_and_slopes():
    p = [50, 60, 70, 80]
    assert trapmf(50, p) == 0 and trapmf(55, p) == pytest.approx(.5) and trapmf(65, p) == 1 and trapmf(75, p) == pytest.approx(.5) and trapmf(90, p) == 0
    assert trapmf(0, [0, 0, 50, 60]) == 1 and trapmf(100, [70, 85, 100, 100]) == 1   # épaulements
    assert trapmf(5, [0, 5, 10]) == 1 and trapmf(2.5, [0, 5, 10]) == pytest.approx(.5)  # triangle

# ---------- référence indépendante (boucles pures, sans numpy vectorisé) ----------
def naive_node(node, values, n=1000):
    degs = {}
    for v in node.in_vars:
        x = values[v.raw_id]
        degs[v.id] = {t.id: float(trapmf(x, t.params)) for t in v.terms}
    zs = [node.out_var.range[0] + i * (node.out_var.range[1] - node.out_var.range[0]) / (n - 1) for i in range(n)]
    num = den = 0.0
    for z in zs:
        agg = 0.0
        for r in node.rb.rules:
            s = min(degs[k][t] for k, t in r["if"].items()) * r.get("weight", 1.0)
            out = trapmf(z, node.out_var.term(list(r["then"].values())[0]).params)
            agg = max(agg, min(s, float(out)))
        num += z * agg; den += agg
    return num / den

def test_cascade_matches_naive_reference(gk, gk_rows):
    for row in gk_rows[:2]:
        vals = dict(row)
        for nid in gk.order:
            node = gk.nodes[nid]
            ref = naive_node(node, vals)
            got = node.run(vals, False)["value"]
            assert got == pytest.approx(ref, abs=1e-9)
            vals[node.out_var.id] = got

# ---------- cas d'école du professeur (arrière latéral) ----------
def test_professor_rules_reproduced_by_generator(lat):
    rb = lat.rulebases["niveau_arriere"]
    lv = {"low": "faible", "high": "fort"}
    expected = {("high","high","high","high"): "niveau6", ("high","high","high","low"): "niveau5",
                ("high","high","low","low"): "niveau4", ("high","low","low","low"): "niveau3",
                ("low","high","low","low"): "niveau2", ("low","low","low","low"): "niveau1"}
    # ordre du prof : vitesse, accélération, tacle, agilité
    tmap = {"low": "faible", "high": "grande"}
    for (v, a, t, g), lvl in expected.items():
        hit = [r for r in rb.rules if r["if"]["vitesse_max"] == v and r["if"]["tacle"] == t
               and r["if"]["acceleration"] == tmap[a] and r["if"]["agilite"] == tmap[g]]
        assert hit[0]["then"]["niveau"] == lvl, (v, a, t, g)

def test_lateral_golden_analytic(lat):
    strong = dict(vitesse_max=40, tacle=95, vitesse_chgt_dir=9, distance_deplacement=8, temps_reaction=0.05, acc_0_5=6, acc_0_10=8)
    weak = dict(vitesse_max=10, tacle=30, vitesse_chgt_dir=1, distance_deplacement=0.5, temps_reaction=0.5, acc_0_5=0.5, acc_0_10=1)
    # centroïde d'un triangle épaulé [80,100,100] et [0,0,20] écrêtés à 1 : (80+100+100)/3 et (0+0+20)/3
    assert lat.score(strong) == pytest.approx(280 / 3, abs=0.05)
    assert lat.score(weak) == pytest.approx(20 / 3, abs=0.05)
    r = lat.evaluate(strong)
    assert r["final"]["level"] == 6 and lat.evaluate(weak)["final"]["level"] == 1

def test_lateral_golden_fixture_file(lat):
    f = ROOT / "data/fixtures/golden/lateral.json"
    for c in json.loads(f.read_text()):
        assert lat.score(c["inputs"]) == pytest.approx(c["expected"], abs=0.5), c["name"]

def test_gardien_golden_fixture_file(gk):
    f = ROOT / "data/fixtures/golden/goalkeeper.json"
    for c in json.loads(f.read_text()):
        assert gk.score(c["inputs"]) == pytest.approx(c["expected"], abs=0.5), c["name"]

def test_shared_variable_two_membership_sets(lat):
    # temps_reaction est lu par deux variables aux fonctions différentes (agilité vs accélération)
    assert "temps_reaction" in lat.required_inputs() and "temps_reaction_acc" not in lat.required_inputs()

# ---------- erreurs et validation ----------
def test_out_of_range_rejected(gk, gk_rows):
    row = dict(gk_rows[0]); row["reflexes"] = 140
    with pytest.raises(ValueError, match="hors plage"):
        gk.evaluate(row)

def test_no_rule_fired_raises(gk, gk_rows):
    from scouting_engine.domain import RuleBase
    rbs = dict(gk.rulebases); r = rbs["ss1_arret_ligne"]
    rbs["ss1_arret_ligne"] = RuleBase(r.id, r.inputs, r.output, [], 1, {})
    with pytest.raises(NoRuleFiredError):
        gk.clone(rulebases=rbs).evaluate(gk_rows[0])

def test_variable_validation_detects_problems(gk):
    for v in gk.variables.values():
        assert validate_variable(v)["ok"], v.id
    bad = gk.variables["reflexes"]
    import copy; b = copy.deepcopy(bad); b.terms[1].params = [60, 50, 80]
    assert not validate_variable(b)["ok"]
    b = copy.deepcopy(bad); b.terms[0].params = [0, 0, 10, 20]; b.terms[1].params = [30, 40, 50]
    assert validate_variable(b)["warnings"]

def test_rulebase_coverage_and_conflicts(gk):
    rb = gk.rulebases["principal"]
    c = check_rulebase(rb, gk.variables)
    assert c["total_combinations"] == 243 and c["coverage"] == 1.0 and not c["conflicts"]
    from scouting_engine.domain import RuleBase
    dup = RuleBase(rb.id, rb.inputs, rb.output, rb.rules + [{**rb.rules[-1], "id": "x", "then": {"note_finale": "niveau1"}}])
    assert check_rulebase(dup, gk.variables)["conflicts"]

def test_rule_counts_match_spec(gk):
    n = {k: len(r.rules) for k, r in gk.rulebases.items() if k not in ("potentiel", "fiabilite")}
    assert sum(n.values()) == 81 + 81 + 27 + 81 + 243

# ---------- propriétés ----------
BASE = dict(reflexes=70, positionnement=6.5, plongeons=6.5, prise_balle=65, jeu_aerien=65, efficacite_1v1=55, anticipation=6.5,
            detente=55, jeu_pied=70, vitesse_reaction=0.25, prise_decision=6.5, communication=6.5, concentration=6.5, mental=6.5,
            regularite=6.5, age=26, minutes_played=1800, league_visibility=6)

def test_deterministic_and_bounded(gk):
    a, b = gk.score(BASE), gk.score(BASE)
    assert a == b and 0 <= a <= 100

@settings(max_examples=40, deadline=None)
@given(var=st.sampled_from([k for k in BASE if k not in ("age", "minutes_played", "league_visibility")]),
       f1=st.floats(0, 1), f2=st.floats(0, 1))
def test_monotonicity(gk, var, f1, f2):
    v = gk.variables[var]; lo, hi = v.range
    x1, x2 = lo + min(f1, f2) * (hi - lo), lo + max(f1, f2) * (hi - lo)
    if v.inverted: x1, x2 = x2, x1            # variable inversée : une valeur plus basse est meilleure
    s_bad, s_good = gk.score({**BASE, var: x1}), gk.score({**BASE, var: x2})
    assert s_good >= s_bad - 1e-6

def test_all_final_scores_in_bounds(gk, gk_rows):
    for r in gk_rows: assert 0 <= gk.score(r) <= 100

def test_performance_under_300ms(gk):
    import time; gk.evaluate_full(BASE); t = time.perf_counter()
    for _ in range(10): gk.evaluate_full(BASE)
    assert (time.perf_counter() - t) / 10 < 0.3

# ---------- modules avancés ----------
def test_reliability_margin_grows_when_playing_time_low(gk):
    lo = gk.evaluate_full({**BASE, "minutes_played": 100, "league_visibility": 2})["reliability"]
    mid = gk.evaluate_full(BASE)["reliability"]
    hi = gk.evaluate_full({**BASE, "minutes_played": 2900, "league_visibility": 9})["reliability"]
    assert lo["margin"] > mid["margin"] > hi["margin"] and lo["index"] < mid["index"] < hi["index"]

def test_potential_differs_with_age(gk):
    young = gk.evaluate_full({**BASE, "age": 19})["age_potential"]["potential"]
    old = gk.evaluate_full({**BASE, "age": 28})["age_potential"]["potential"]
    assert young > old

def test_sensitivity(gk):
    from scouting_engine.sensitivity import sensitivity
    r = sensitivity(gk, BASE, "jeu_pied", 5)
    assert r["new_value"] == 75 and r["delta_score"] >= 0

def test_fcm_reproducible_and_similarity(gk, gk_rows):
    from scouting_engine.fcm import fcm, normalize, similar
    ids = [i for i in gk.required_inputs() if i not in ("age", "minutes_played", "league_visibility")]
    X = np.array([normalize(gk, r, ids) for r in gk_rows])
    C1, U1, f1 = fcm(X, 3, seed=1); C2, U2, f2 = fcm(X, 3, seed=1)
    assert np.allclose(C1, C2) and np.allclose(U1.sum(axis=0), 1) and 1 / 3 <= f1 <= 1
    for metric in ("cosine", "euclid"):
        s = similar(gk, gk_rows[3], gk_rows, metric=metric, k=3)
        assert s[0]["id"] == gk_rows[3]["id"] and s[0]["distance"] == pytest.approx(0, abs=1e-9)

def test_ga_improves_validation_error(gk, gk_rows):
    from scouting_engine.ga import optimize
    y = [r["expert_note"] for r in gk_rows]
    res = optimize(gk, gk_rows, y, seed=7, pop=10, gens=6)
    assert res["train_mse_after"] <= res["train_mse_before"] + 1e-9
    assert res["val_mse_after"] <= res["val_mse_before"] * 1.05

def test_comment_has_3_to_6_sentences(gk):
    from scouting_engine.explain import comment
    r = gk.evaluate_full(BASE); txt = comment(gk, BASE, r)
    assert 3 <= txt.count(". ") + 1 <= 6
