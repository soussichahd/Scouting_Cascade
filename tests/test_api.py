import os, tempfile, pathlib, pytest
os.environ["DB_PATH"] = str(pathlib.Path(tempfile.mkdtemp()) / "t.db")
from fastapi.testclient import TestClient
from api.app import app
from tests.test_engine import BASE

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c: yield c

def test_evaluation_contract(client):
    r = client.post("/evaluations", json={"goalkeeper": {"age": 24, "minutes_played": 1800, "league_visibility": 6}, "inputs": {k: v for k, v in BASE.items() if k not in ("age", "minutes_played", "league_visibility")}, "rulebase_version": "active"})
    assert r.status_code == 200, r.text; j = r.json()
    assert len(j["subscores"]) == 4 and 0 <= j["final"]["score"] <= 100 and len(j["final"]["degrees"]) == 6
    assert j["reliability"]["margin"] > 0 and "potential" in j["age_potential"] and j["trace"]["main"]["fired_rules"] and j["comment"]

def test_out_of_range_422_french(client):
    r = client.post("/evaluations", json={"inputs": {**BASE, "reflexes": 999}})
    assert r.status_code == 422 and "hors plage" in r.json()["detail"]

def test_version_edit_ab_and_activate(client):
    rb = client.get("/rulebases/principal").json(); rules = rb["rules"]
    base = client.post("/evaluations", json={"inputs": BASE}).json()["final"]["score"]
    rules = [{**r, "then": {"note_finale": "niveau1"}, "author": "expert"} if r["id"] == rules[-1]["id"] else r for r in rules]
    new = client.put("/rulebases/principal", json={"rules": rules, "author": "expert", "comment": "test sévère", "activate": False}).json()
    assert new["version"] == 2 and not new["active"]
    ab = client.post("/ab-tests", json={"rulebase": "principal", "version_a": 1, "version_b": 2}).json()
    assert len(ab["rows"]) == 60 and client.get(f"/ab-tests/{ab['id']}/csv").status_code == 200
    assert len(client.get("/rulebases/principal/versions").json()) == 2          # immuable : v1 toujours là
    client.post("/rulebases/principal/versions/2/activate")
    assert client.get("/rulebases/principal/versions").json()[0]["active"] == 1
    client.post("/rulebases/principal/versions/1/activate")                      # retour arrière
    assert client.post("/evaluations", json={"inputs": BASE}).json()["final"]["score"] == pytest.approx(base)

def test_variable_edit_validation(client):
    v = next(x for x in client.get("/variables").json()["variables"] if x["id"] == "reflexes")
    bad = {**v, "terms": [{**v["terms"][0], "params": [0, 0, 60, 50]}] + v["terms"][1:]}
    assert client.put("/variables/reflexes", json=bad).status_code == 422
    ok = {**v, "terms": [{**v["terms"][0], "params": [0, 0, 52, 62]}] + v["terms"][1:]}
    assert client.put("/variables/reflexes", json=ok).status_code == 200

def test_save_report_similar_profiles(client):
    e = client.post("/evaluations", json={"goalkeeper_id": "gk01", "save": True, "inputs": {**BASE}}).json()
    pdf = client.get(f"/evaluations/{e['evaluation_id']}/report.pdf"); assert pdf.content[:4] == b"%PDF"
    assert len(client.get("/goalkeepers/gk01/evaluations").json()) == 1
    s = client.post("/goalkeepers/similar", json={"goalkeeper_id": "gk05", "k": 3}).json(); assert s[0]["id"] == "gk05"
    p = client.get("/profiles?c=3").json(); assert len(p["profiles"]) == 3 and len(p["memberships"]) == 60
    assert client.post("/evaluations/sensitivity", json={"inputs": BASE, "variable": "jeu_pied", "delta": 5}).json()["delta_score"] >= 0
