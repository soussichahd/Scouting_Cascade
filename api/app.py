"""API FastAPI : évaluation, édition des variables/règles (versions immuables), A/B, gardiens, similarité, FCM, PDF."""
import csv, io, json, threading
from pathlib import Path
import numpy as np, yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from scouting_engine import Model, NoRuleFiredError
from scouting_engine.domain import RuleBase, variable_from_dict, variable_to_dict
from scouting_engine.explain import comment as make_comment
from scouting_engine.sensitivity import sensitivity
from scouting_engine.rulegen import generate_rules
from scouting_engine.validation import validate_variable, check_rulebase
from scouting_engine.fcm import fcm, normalize, similar, auto_names
from scouting_engine.ga import optimize
from . import db
from .report import build_pdf

app = FastAPI(title="Scouting gardien – SIF Mamdani en cascade", version="1.0")
CASCADE = yaml.safe_load((db.SEED / "cascade.yaml").read_text(encoding="utf-8"))
NODE_BY_RB = {n["rulebase"]: n for n in CASCADE["nodes"] + CASCADE.get("parallel", [])}
_lock, _cache = threading.Lock(), {}
EXTRA = ("age", "minutes_played", "league_visibility")

@app.on_event("startup")
def _startup(): db.init()

@app.exception_handler(ValueError)
async def _ve(_, e): return JSONResponse({"detail": str(e)}, status_code=422)
@app.exception_handler(NoRuleFiredError)
async def _nr(_, e): return JSONResponse({"detail": str(e)}, status_code=409)

# ---------- construction du modèle depuis la base ----------
def _variables(c, version=None):
    r = c.execute("SELECT * FROM variable_versions WHERE " + ("version=?" if version else "active=1"), (version,) if version else ()).fetchone()
    return r["version"], {v["id"]: variable_from_dict(v) for v in json.loads(r["data"])}
def _rb_row(c, rb, version=None):
    r = c.execute("SELECT * FROM rulebase_versions WHERE rulebase=? AND " + ("version=?" if version else "active=1"), (rb, version) if version else (rb,)).fetchone()
    if not r: raise HTTPException(404, f"Base de règles « {rb} » (version {version or 'active'}) introuvable")
    return r
def get_model(override=None, var_version=None, n_points=1000):
    """override = {rulebase: version} pour tester une version précise sans l'activer."""
    override = override or {}
    c = db.conn(); vv, V = _variables(c, var_version); rbs, vers = {}, {}
    for rb, n in NODE_BY_RB.items():
        r = _rb_row(c, rb, override.get(rb)); vers[rb] = r["version"]
        rbs[rb] = RuleBase(rb, n["inputs"], n["output"], json.loads(r["rules"]), r["version"], json.loads(r["gen"] or "{}"))
    c.close(); key = (vv, tuple(sorted(vers.items())), n_points)
    with _lock:
        if key not in _cache:
            if len(_cache) > 12: _cache.clear()
            _cache[key] = Model(V, CASCADE, rbs, n_points)
        return _cache[key], {"variables": vv, **vers}

def _split(body):
    gk = body.get("goalkeeper", {}) or {}; inp = dict(body.get("inputs", {}))
    for k in EXTRA:
        if k in gk and k not in inp: inp[k] = gk[k]
    return inp

# ---------- évaluation ----------
@app.get("/meta")
def meta():
    m, v = get_model()
    return {"inputs": [variable_to_dict(m.variables[i]) for i in m.required_inputs()], "cascade": CASCADE, "versions": v,
            "levels": [t.label for t in m.variables["note_finale"].terms], "sub_ids": [n["output"] for n in CASCADE["nodes"] if n["id"] != CASCADE["final"]]}

@app.post("/evaluations")
def evaluate(body: dict):
    ver = body.get("rulebase_version", "active")
    ov = {} if ver == "active" else body.get("rulebase_versions", {})
    m, vers = get_model(ov); inp = _split(body)
    res = m.evaluate_full(inp); txt = make_comment(m, inp, res)
    out = {"subscores": res["subscores"], "final": res["final"], "reliability": res.get("reliability"), "age_potential": res["age_potential"],
           "trace": res["trace"], "comment": txt, "versions": vers}
    if body.get("save") and body.get("goalkeeper_id"):
        c = db.conn(); cur = c.execute("INSERT INTO evaluations(goalkeeper_id,inputs,versions,output,comment,created) VALUES(?,?,?,?,?,?)",
                    (body["goalkeeper_id"], json.dumps(inp), json.dumps(vers), json.dumps({k: out[k] for k in ("subscores", "final", "reliability", "age_potential")}), txt, db.now()))
        out["evaluation_id"] = cur.lastrowid; c.commit(); c.close()
    return out

@app.post("/evaluations/sensitivity")
def sens(body: dict):
    m, _ = get_model(); return sensitivity(m, _split(body), body["variable"], float(body["delta"]), body.get("mode", "absolute"))

@app.get("/evaluations/{eid}/report.pdf")
def report(eid: int):
    c = db.conn(); e = c.execute("SELECT * FROM evaluations WHERE id=?", (eid,)).fetchone()
    if not e: raise HTTPException(404, "Évaluation introuvable")
    g = c.execute("SELECT name FROM goalkeepers WHERE id=?", (e["goalkeeper_id"],)).fetchone(); c.close()
    vers = json.loads(e["versions"]); m, _ = get_model({k: v for k, v in vers.items() if k != "variables"}, vers.get("variables"))
    res = m.evaluate_full(json.loads(e["inputs"]))     # rejoué (ENF-4) pour disposer de la trace
    pdf = build_pdf(g["name"] if g else e["goalkeeper_id"], res, e["comment"], m, ", ".join(f"{k}:v{v}" for k, v in vers.items() if k != "variables"), json.loads(e["inputs"]), e["created"])
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename=rapport_{eid}.pdf"})

# ---------- variables ----------
@app.get("/variables")
def list_vars():
    c = db.conn(); vv, V = _variables(c); c.close()
    return {"version": vv, "variables": [variable_to_dict(v) for v in V.values()]}
@app.post("/variables/validate")
def val_var(body: dict): return validate_variable(variable_from_dict(body))
@app.put("/variables/{vid}")
def put_var(vid: str, body: dict):
    c = db.conn(); row = c.execute("SELECT * FROM variable_versions WHERE active=1").fetchone(); data = json.loads(row["data"])
    body["id"] = vid; v = variable_from_dict(body); chk = validate_variable(v)
    if not chk["ok"]: raise HTTPException(422, "; ".join(chk["errors"]))
    data = [variable_to_dict(v) if d["id"] == vid else d for d in data]
    nv = c.execute("SELECT MAX(version) FROM variable_versions").fetchone()[0] + 1
    c.execute("UPDATE variable_versions SET active=0")
    c.execute("INSERT INTO variable_versions(version,data,author,comment,created,active) VALUES(?,?,?,?,?,1)", (nv, json.dumps(data, ensure_ascii=False), body.get("author", "expert"), body.get("comment", f"modif {vid}"), db.now()))
    c.commit(); c.close(); return {"version": nv, **chk}

# ---------- règles ----------
def _check(rb, rules):
    m, _ = get_model(); n = NODE_BY_RB[rb]
    return check_rulebase(RuleBase(rb, n["inputs"], n["output"], rules), m.variables)
@app.get("/rulebases")
def list_rb():
    c = db.conn(); out = []
    for rb, n in NODE_BY_RB.items():
        r = _rb_row(c, rb); out.append({"id": rb, "node": n["id"], "inputs": n["inputs"], "output": n["output"], "active_version": r["version"], "n_rules": len(json.loads(r["rules"]))})
    c.close(); return out
@app.get("/rulebases/{rb}/versions")
def rb_versions(rb: str):
    c = db.conn(); rows = c.execute("SELECT version,author,comment,created,active FROM rulebase_versions WHERE rulebase=? ORDER BY version DESC", (rb,)).fetchall(); c.close()
    return [dict(r) for r in rows]
@app.get("/rulebases/{rb}")
def get_rb(rb: str, version: int | None = None):
    c = db.conn(); r = _rb_row(c, rb, version); c.close(); rules = json.loads(r["rules"])
    return {"id": rb, "version": r["version"], "active": bool(r["active"]), "gen": json.loads(r["gen"] or "{}"), "rules": rules, "check": _check(rb, rules), **{k: NODE_BY_RB[rb][k] for k in ("inputs", "output")}}
@app.put("/rulebases/{rb}")
def put_rb(rb: str, body: dict):
    """Crée une nouvelle version (jamais d'écrasement). body: {rules, gen?, author, comment, activate?}"""
    rules = body["rules"]; chk = _check(rb, rules)
    c = db.conn(); nv = c.execute("SELECT COALESCE(MAX(version),0) FROM rulebase_versions WHERE rulebase=?", (rb,)).fetchone()[0] + 1
    act = 1 if body.get("activate", True) else 0
    if act: c.execute("UPDATE rulebase_versions SET active=0 WHERE rulebase=?", (rb,))
    c.execute("INSERT INTO rulebase_versions(rulebase,version,rules,gen,author,comment,created,active) VALUES(?,?,?,?,?,?,?,?)",
              (rb, nv, json.dumps(rules, ensure_ascii=False), json.dumps(body.get("gen", {})), body.get("author", "expert"), body.get("comment", ""), db.now(), act))
    c.commit(); c.close(); return {"version": nv, "active": bool(act), "check": chk}
@app.post("/rulebases/{rb}/versions/{v}/activate")
def activate(rb: str, v: int):
    c = db.conn(); _rb_row(c, rb, v); c.execute("UPDATE rulebase_versions SET active=(version=?) WHERE rulebase=?", (v, rb)); c.commit(); c.close(); return {"active_version": v}
@app.post("/rulebases/generate")
def generate(body: dict):
    rb = body["rulebase"]; n = NODE_BY_RB[rb]; m, _ = get_model(); gen = {"weights": body.get("weights", {}), "ranks": body.get("ranks", {})}
    rules = generate_rules(rb, [m.variables[i] for i in n["inputs"]], m.variables[n["output"]], gen)
    return {"gen": gen, "rules": rules, "check": _check(rb, rules)}

# ---------- gardiens ----------
def _gk(r): return {"id": r["id"], "name": r["name"], "club": r["club"], "age": r["age"], "league_visibility": r["league_visibility"], "minutes_played": r["minutes_played"], "stats": json.loads(r["stats"]), "expert_note": r["expert_note"]}
def _inputs(g): return {**g["stats"], "age": g["age"], "minutes_played": g["minutes_played"], "league_visibility": g["league_visibility"]}
@app.get("/goalkeepers")
def list_gk():
    c = db.conn(); rows = c.execute("SELECT * FROM goalkeepers ORDER BY id").fetchall(); c.close(); m, _ = get_model()
    out = []
    for r in rows:
        g = _gk(r); g["score"] = m.score(_inputs(g)); out.append(g)
    return out
@app.post("/goalkeepers")
def upsert_gk(body: dict):
    gid = body.get("id") or f"gk_{int(__import__('time').time())}"; st = body.get("stats", {})
    c = db.conn(); c.execute("INSERT OR REPLACE INTO goalkeepers VALUES(?,?,?,?,?,?,?,?)", (gid, body["name"], body.get("club", ""), body["age"], body.get("league_visibility", 5), body.get("minutes_played", 0), json.dumps(st), body.get("expert_note")))
    c.commit(); c.close(); return {"id": gid}
@app.get("/goalkeepers/{gid}/evaluations")
def gk_evals(gid: str):
    c = db.conn(); rows = c.execute("SELECT id,created,versions,output,comment FROM evaluations WHERE goalkeeper_id=? ORDER BY id", (gid,)).fetchall(); c.close()
    return [{"id": r["id"], "created": r["created"], "versions": json.loads(r["versions"]), "output": json.loads(r["output"]), "comment": r["comment"]} for r in rows]
@app.post("/goalkeepers/similar")
def sim(body: dict):
    c = db.conn(); pool = [_gk(r) for r in c.execute("SELECT * FROM goalkeepers").fetchall()]; c.close(); m, _ = get_model()
    P = [{"id": g["id"], "name": g["name"], **_inputs(g)} for g in pool]
    tgt = next(p for p in P if p["id"] == body["goalkeeper_id"]) if body.get("goalkeeper_id") else {**_split(body), "id": None, "name": "saisie"}
    return similar(m, tgt, P, body.get("metric", "cosine"), body.get("space", "variables"), int(body.get("k", 5)))
@app.get("/profiles")
def profiles(c: int = 3, seed: int = 42):
    cn = db.conn(); pool = [_gk(r) for r in cn.execute("SELECT * FROM goalkeepers ORDER BY id").fetchall()]; cn.close(); m, _ = get_model()
    ids = [i for i in m.required_inputs() if i not in EXTRA]
    X = np.array([normalize(m, _inputs(g), ids) for g in pool]); C, U, fpc = fcm(X, c, seed=seed)
    names = auto_names(C, ids, {i: m.variables[i].label for i in ids})
    return {"fpc": fpc, "seed": seed, "profiles": [{"name": names[k], "center": dict(zip(ids, C[k].round(3).tolist()))} for k in range(c)],
            "memberships": [{"id": g["id"], "name": g["name"], "u": U[:, i].round(3).tolist()} for i, g in enumerate(pool)]}

# ---------- A/B ----------
@app.post("/ab-tests")
def ab(body: dict):
    rb, va, vb = body["rulebase"], int(body["version_a"]), int(body["version_b"])
    ma, _ = get_model({rb: va}); mb, _ = get_model({rb: vb})
    c = db.conn(); pool = [_gk(r) for r in c.execute("SELECT * FROM goalkeepers ORDER BY id").fetchall()]; c.close()
    if body.get("goalkeeper_ids"): pool = [g for g in pool if g["id"] in body["goalkeeper_ids"]]
    rows = []
    for g in pool:
        ra, r2 = ma.evaluate(_inputs(g)), mb.evaluate(_inputs(g))
        fa = {(n, r["id"]) for n, t in ra["trace"].items() if t for r in t["fired_rules"]}; fb = {(n, r["id"]) for n, t in r2["trace"].items() if t for r in t["fired_rules"]}
        rows.append({"id": g["id"], "name": g["name"], "score_a": ra["final"]["score"], "score_b": r2["final"]["score"], "delta": r2["final"]["score"] - ra["final"]["score"],
                     "rules_differ": sorted(f"{n}:{i}" for n, i in fa ^ fb)})
    c = db.conn(); cur = c.execute("INSERT INTO ab_tests(rulebase,version_a,version_b,results,created) VALUES(?,?,?,?,?)", (rb, va, vb, json.dumps(rows), db.now())); c.commit(); c.close()
    return {"id": cur.lastrowid, "rows": rows, "mean_abs_delta": float(np.mean([abs(r["delta"]) for r in rows]))}
@app.get("/ab-tests/{tid}/csv")
def ab_csv(tid: int):
    c = db.conn(); r = c.execute("SELECT * FROM ab_tests WHERE id=?", (tid,)).fetchone(); c.close()
    if not r: raise HTTPException(404, "Test introuvable")
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(["id", "nom", f"note_v{r['version_a']}", f"note_v{r['version_b']}", "ecart", "regles_qui_different"])
    for x in json.loads(r["results"]): w.writerow([x["id"], x["name"], f"{x['score_a']:.2f}", f"{x['score_b']:.2f}", f"{x['delta']:.2f}", ";".join(x["rules_differ"])])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=ab_{tid}.csv"})

# ---------- calibration GA (priorité C) ----------
@app.post("/optimize")
def calibrate(body: dict):
    m, _ = get_model(); c = db.conn(); pool = [_gk(r) for r in c.execute("SELECT * FROM goalkeepers WHERE expert_note IS NOT NULL").fetchall()]; c.close()
    res = optimize(m, [_inputs(g) for g in pool], [g["expert_note"] for g in pool], seed=int(body.get("seed", 42)), pop=int(body.get("pop", 12)), gens=int(body.get("gens", 8)))
    new = res.pop("model")
    if body.get("apply"):
        for n in CASCADE["nodes"]:
            rb = new.rulebases[n["rulebase"]]; put_rb(n["rulebase"], {"rules": rb.rules, "gen": rb.gen, "author": "ga", "comment": f"calibration GA seed={res['seed']}"})
    return res

web = Path(__file__).resolve().parents[1] / "web"
@app.get("/")
def index(): return FileResponse(web / "index.html")
if web.exists(): app.mount("/static", StaticFiles(directory=web), name="static")
