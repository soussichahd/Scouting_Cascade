"""Génère data/seed/{goalkeeper,lateral}/ : variables.yaml, cascade.yaml, rulebases/*.yaml.
Les bases de règles sont produites par le générateur pondéré (rulegen) ; l'expert corrige ensuite à la main."""
import sys, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "src"))
from scouting_engine.domain import variable_from_dict
from scouting_engine.rulegen import generate_rules

def T(i, l, p): return {"id": i, "label": l, "shape": "triangle" if len(p) == 3 else "trapezoid", "params": p}
def V(id, label, unit, rng, terms, **kw): return {"id": id, "label": label, "unit": unit, "range": rng, "terms": terms, **kw}
def FMF(id, label, unit, rng, low, mid, high, names=("Faible", "Moyen", "Fort"), ids=("low", "mid", "high"), **kw):
    return V(id, label, unit, rng, [T(ids[0], names[0], low), T(ids[1], names[1], mid), T(ids[2], names[2], high)], **kw)
SUB = lambda id, label: V(id, label, "", [0, 10], [T("faible", "Faible", [0,0,3,5]), T("moyenne", "Moyenne", [3,5,6,8]), T("grande", "Grande", [6,8,10,10])], kind="output")
LEVELS = [T("niveau1","Niveau 1",[0,0,20]), T("niveau2","Niveau 2",[0,20,40]), T("niveau3","Niveau 3",[20,40,60]),
          T("niveau4","Niveau 4",[40,60,80]), T("niveau5","Niveau 5",[60,80,100]), T("niveau6","Niveau 6",[80,100,100])]
LEVEL = lambda id, label: V(id, label, "/100", [0, 100], LEVELS, kind="output")

def write(name, variables, cascade, gens):
    d = ROOT / "data" / "seed" / name
    (d / "rulebases").mkdir(parents=True, exist_ok=True)
    (d / "variables.yaml").write_text(yaml.safe_dump({"variables": variables}, allow_unicode=True, sort_keys=False, default_flow_style=None), encoding="utf-8")
    (d / "cascade.yaml").write_text(yaml.safe_dump(cascade, allow_unicode=True, sort_keys=False, default_flow_style=None), encoding="utf-8")
    vs = {v["id"]: variable_from_dict(v) for v in variables}
    for n in cascade["nodes"] + cascade.get("parallel", []):
        gen = gens[n["rulebase"]]
        rules = generate_rules(n["rulebase"], [vs[i] for i in n["inputs"]], vs[n["output"]], gen)
        (d / "rulebases" / f"{n['rulebase']}.yaml").write_text(yaml.safe_dump(
            {"rule_base": n["rulebase"], "version": 1, "gen": gen, "rules": rules}, allow_unicode=True, sort_keys=False, default_flow_style=None), encoding="utf-8")

# ---------------- GARDIEN ----------------
def trio(low_end, mid, high_start):  # helper non utilisé
    pass
gk_vars = [
 FMF("reflexes","Réflexes","% d'arrêts",[0,100],[0,0,50,60],[50,65,80],[70,85,100,100]),
 FMF("positionnement","Positionnement","score",[0,10],[0,0,4,5.5],[4,5.5,7],[5.5,7.5,10,10]),
 FMF("prise_balle","Prise de balle","% bloqué",[0,100],[0,0,40,50],[40,60,80],[70,85,100,100]),
 FMF("plongeons","Plongeons","score",[0,10],[0,0,4,5],[4,5.5,7],[6,7.5,10,10]),
 FMF("jeu_aerien","Jeu aérien","% gagnés",[0,100],[0,0,45,60],[45,60,75],[65,80,100,100]),
 FMF("efficacite_1v1","Efficacité 1v1","% arrêts",[0,100],[0,0,30,45],[30,50,70],[55,75,100,100]),
 FMF("anticipation","Anticipation","score",[0,10],[0,0,4,6],[4,6,8],[6,8,10,10]),
 FMF("detente","Détente / puissance","cm",[0,100],[0,0,40,50],[40,55,70],[60,75,100,100]),
 FMF("jeu_pied","Jeu au pied","% passes",[0,100],[0,0,55,65],[55,70,85],[75,85,100,100]),
 FMF("vitesse_reaction","Vitesse de réaction","s",[0.1,0.6],[0.1,0.1,0.2,0.3],[0.2,0.3,0.4],[0.3,0.45,0.6,0.6],
     names=("Rapide","Moyen","Lent"),ids=("fast","mid","slow"),inverted=True),
 FMF("prise_decision","Prise de décision","score",[0,10],[0,0,4,5.5],[4,5.5,7.5],[6,8,10,10]),
 FMF("communication","Communication","score",[0,10],[0,0,3,5],[3,5.5,7],[6,7.5,10,10]),
 FMF("concentration","Concentration","score",[0,10],[0,0,4,6],[4,6,8],[6,8,10,10]),
 FMF("mental","Mental (clutch)","score",[0,10],[0,0,4,5],[4,6,8],[7,8.5,10,10]),
 FMF("regularite","Régularité","score",[0,10],[0,0,5,6],[5,6.5,8],[7,8.5,10,10]),
 V("age","Âge","ans",[15,45],[T("jeune","Jeune",[15,15,20,25]),T("confirme","Confirmé",[20,25,30,35]),T("experimente","Expérimenté",[30,35,45,45])]),
 V("minutes_played","Temps de jeu","min",[0,3000],[T("faible","Faible",[0,0,500,1200]),T("moyen","Moyen",[500,1200,1800,2400]),T("eleve","Élevé",[1800,2500,3000,3000])]),
 FMF("league_visibility","Visibilité de la ligue","score",[0,10],[0,0,3,5],[3,5,7],[5,7,10,10],names=("Faible","Moyenne","Haute")),
 SUB("sous_score_ss1","Sous-score Arrêt et ligne"), SUB("sous_score_ss2","Sous-score Surface et air"),
 SUB("sous_score_ss3","Sous-score Relance et jeu"), SUB("sous_score_ss4","Sous-score Mental et leadership"),
 LEVEL("note_finale","Note finale"),
 LEVEL("potentiel","Potentiel futur"),
 V("fiabilite","Indice de fiabilité","",[0,1],[T("faible","Faible",[0,0,0.3,0.5]),T("moyenne","Moyenne",[0.3,0.5,0.7]),T("haute","Haute",[0.5,0.7,1,1])],kind="output"),
]
gk_cascade = {"nodes": [
 {"id":"ss1","inputs":["reflexes","positionnement","plongeons","prise_balle"],"output":"sous_score_ss1","rulebase":"ss1_arret_ligne"},
 {"id":"ss2","inputs":["jeu_aerien","efficacite_1v1","anticipation","detente"],"output":"sous_score_ss2","rulebase":"ss2_surface_air"},
 {"id":"ss3","inputs":["jeu_pied","vitesse_reaction","prise_decision"],"output":"sous_score_ss3","rulebase":"ss3_relance_jeu"},
 {"id":"ss4","inputs":["communication","concentration","mental","regularite"],"output":"sous_score_ss4","rulebase":"ss4_mental"},
 {"id":"main","inputs":["sous_score_ss1","sous_score_ss2","sous_score_ss3","sous_score_ss4","age"],"output":"note_finale","rulebase":"principal"}],
 "final":"main",
 "parallel":[
 {"id":"potential","inputs":["sous_score_ss1","sous_score_ss2","sous_score_ss3","sous_score_ss4","age"],"output":"potentiel","rulebase":"potentiel"},
 {"id":"reliability","inputs":["minutes_played","league_visibility"],"output":"fiabilite","rulebase":"fiabilite"}],
 "settings":{"max_margin":15.0}}
gk_gens = {
 "ss1_arret_ligne":{"weights":{"reflexes":.35,"positionnement":.25,"plongeons":.20,"prise_balle":.20}},
 "ss2_surface_air":{"weights":{"jeu_aerien":.30,"efficacite_1v1":.35,"anticipation":.20,"detente":.15}},
 "ss3_relance_jeu":{"weights":{"jeu_pied":.40,"vitesse_reaction":.30,"prise_decision":.30}},
 "ss4_mental":{"weights":{"communication":.25,"concentration":.25,"mental":.25,"regularite":.25}},
 "principal":{"weights":{"sous_score_ss1":.30,"sous_score_ss2":.25,"sous_score_ss3":.20,"sous_score_ss4":.17,"age":.08},
              "ranks":{"age":{"jeune":0.3,"confirme":1.0,"experimente":0.8}}},
 "potentiel":{"weights":{"sous_score_ss1":.22,"sous_score_ss2":.18,"sous_score_ss3":.15,"sous_score_ss4":.15,"age":.30},
              "ranks":{"age":{"jeune":1.0,"confirme":0.5,"experimente":0.0}}},
 "fiabilite":{"weights":{"minutes_played":.6,"league_visibility":.4}}}
write("goalkeeper", gk_vars, gk_cascade, gk_gens)

# ---------------- ARRIÈRE LATÉRAL (cas du professeur) ----------------
def F3(id,label,unit,rng,p,hi,names=("Faible","Moyen","Fort"),ids=("low","mid","high"),**kw):
    a,b,c,d = p
    return FMF(id,label,unit,rng,[rng[0],rng[0],a,b],[a,b,c,d],[c,d,hi,hi],names=names,ids=ids,**kw)
RT = dict(names=("Rapide","Moyen","Lent"),ids=("fast","mid","slow"),inverted=True)
lat_vars = [
 F3("vitesse_max","Vitesse maximale","km/h",[0,45],[20,25,30,35],45),
 V("tacle","Tacle","% réussite",[0,100],[T("low","Niveau national",[0,0,60,70]),T("mid","Niveau professionnel",[60,70,80,90]),T("high","Niveau international",[80,90,100,100])]),
 F3("vitesse_chgt_dir","Vitesse de changement de direction","m/s",[0,10],[2,4,6,8],10),
 F3("distance_deplacement","Distance de déplacement (agilité)","m",[0,10],[1,2,4,6],10),
 F3("temps_reaction","Temps de réaction (agilité)","s",[0,0.6],[0.1,0.2,0.3,0.4],0.6,**RT),
 F3("acc_0_5","Accélération 0-5 m","m/s²",[0,8],[1.5,2.5,3.5,4],8),
 F3("acc_0_10","Accélération 0-10 m","m/s²",[0,10],[2.5,3.5,4.5,6],10),
 F3("temps_reaction_acc","Temps de réaction (accélération)","s",[0,0.6],[0.09,0.15,0.25,0.4],0.6,source="temps_reaction",**RT),
 F3("distance_acc","Distance de déplacement (accélération)","m",[0,10],[2,4,6,8],10,source="distance_deplacement"),
 SUB("agilite","Agilité"), SUB("acceleration","Accélération"),
 LEVEL("niveau","Niveau"),
]
lat_cascade = {"nodes":[
 {"id":"agilite","inputs":["vitesse_chgt_dir","distance_deplacement","temps_reaction","vitesse_max"],"output":"agilite","rulebase":"agilite"},
 {"id":"acceleration","inputs":["vitesse_max","acc_0_5","acc_0_10","temps_reaction_acc","distance_acc"],"output":"acceleration","rulebase":"acceleration"},
 {"id":"main","inputs":["vitesse_max","acceleration","tacle","agilite"],"output":"niveau","rulebase":"niveau_arriere"}],"final":"main"}
lat_gens = {"agilite":{"weights":{}},"acceleration":{"weights":{}},
            "niveau_arriere":{"weights":{"vitesse_max":.40,"acceleration":.20,"tacle":.25,"agilite":.15}}}
write("lateral", lat_vars, lat_cascade, lat_gens)
print("seed OK")
