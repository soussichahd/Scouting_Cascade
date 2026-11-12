"""Génère 60 gardiens FICTIFS (documentés comme tels) + notes d'experts simulées (poids différents + bruit)."""
import sys, csv
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "engine/src"))
from scouting_engine import Model
from scouting_engine.ga import _genes, build_with_weights
rng = np.random.default_rng(2026)
m = Model.from_dir(ROOT / "data/seed/goalkeeper")
VARS = [i for i in m.required_inputs() if i not in ("age", "minutes_played", "league_visibility")]
# archétypes en [0,1] « favorable » par sous-score : (ss1, ss2, ss3, ss4)
ARCH = {"complet": (.8,.8,.75,.8), "libero": (.55,.55,.9,.65), "sur-sa-ligne": (.9,.5,.4,.65), "jeune-prometteur": (.55,.6,.55,.5),
        "moyen": (.5,.5,.5,.5), "limite": (.3,.3,.3,.35), "dominant-air": (.6,.9,.55,.7)}
GRP = {"reflexes":0,"positionnement":0,"plongeons":0,"prise_balle":0,"jeu_aerien":1,"efficacite_1v1":1,"anticipation":1,"detente":1,
       "jeu_pied":2,"vitesse_reaction":2,"prise_decision":2,"communication":3,"concentration":3,"mental":3,"regularite":3}
first = ["Adam","Yanis","Karim","Lucas","Marc","Oscar","Hugo","Ilyes","Noah","Samir","Tom","Elias","Rayan","Axel","Mehdi"]
last = ["Berthier","Lakhal","Moretti","Dubreuil","Haddad","Costa","Vidal","Okafor","Nilsen","Barka","Lemaire","Sorel"]
clubs = ["FC Aurore","AS Littoral","US Montagne","Olympique Nord","SC Atlas","RC Delta"]
expert = build_with_weights(m, _genes(m), [{"ss1_arret_ligne:reflexes":.3,"ss1_arret_ligne:positionnement":.3,"ss1_arret_ligne:plongeons":.2,"ss1_arret_ligne:prise_balle":.2,
    "ss2_surface_air:jeu_aerien":.25,"ss2_surface_air:efficacite_1v1":.4,"ss2_surface_air:anticipation":.25,"ss2_surface_air:detente":.1,
    "ss3_relance_jeu:jeu_pied":.35,"ss3_relance_jeu:vitesse_reaction":.35,"ss3_relance_jeu:prise_decision":.3,
    "ss4_mental:communication":.2,"ss4_mental:concentration":.3,"ss4_mental:mental":.3,"ss4_mental:regularite":.2,
    "principal:sous_score_ss1":.34,"principal:sous_score_ss2":.24,"principal:sous_score_ss3":.16,"principal:sous_score_ss4":.18,"principal:age":.08}.get(f"{rb}:{v}", 0.2)
    for rb, v in _genes(m)])
rows = []
for k in range(60):
    a = list(ARCH)[k % len(ARCH)]; base = ARCH[a]
    r = {"id": f"gk{k+1:02d}", "name": f"{first[k % 15]} {last[(k*7) % 12]} (fictif)", "archetype": a,
         "club": clubs[k % 6], "age": int(rng.integers(18, 38) if a != "jeune-prometteur" else rng.integers(17, 22)),
         "minutes_played": int(rng.integers(200, 3000)), "league_visibility": round(float(rng.uniform(1, 10)), 1)}
    for vid in VARS:
        v = m.variables[vid]; lo, hi = v.range
        f = float(np.clip(base[GRP[vid]] + rng.normal(0, 0.12), 0.02, 0.98))
        f = 1 - f if v.inverted else f
        r[vid] = round(lo + f * (hi - lo), 3 if hi < 1 else 1)
    inp = {k2: r[k2] for k2 in r if k2 not in ("id", "name", "archetype", "club")}
    r["expert_note"] = round(float(np.clip(expert.score(inp) + rng.normal(0, 2.0), 0, 100)), 1)
    rows.append(r)
out = ROOT / "data/fixtures/goalkeepers/goalkeepers.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("écrit", out, len(rows))
