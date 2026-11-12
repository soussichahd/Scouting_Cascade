"""Persistance SQLite (versions immuables). Schéma identique dans l'esprit à la section 9.4 ; PostgreSQL = changement de driver."""
import csv, json, os, sqlite3, datetime as dt
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data/seed/goalkeeper"
DB_PATH = Path(os.environ.get("DB_PATH", ROOT / "data/app.db"))
META = ("id", "name", "archetype", "club", "expert_note")

def now(): return dt.datetime.now().isoformat(timespec="seconds")

def conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False); c.row_factory = sqlite3.Row
    return c

SCHEMA = """
CREATE TABLE IF NOT EXISTS rulebase_versions(id INTEGER PRIMARY KEY, rulebase TEXT, version INT, rules TEXT, gen TEXT, author TEXT, comment TEXT, created TEXT, active INT, UNIQUE(rulebase,version));
CREATE TABLE IF NOT EXISTS variable_versions(id INTEGER PRIMARY KEY, version INT UNIQUE, data TEXT, author TEXT, comment TEXT, created TEXT, active INT);
CREATE TABLE IF NOT EXISTS goalkeepers(id TEXT PRIMARY KEY, name TEXT, club TEXT, age REAL, league_visibility REAL, minutes_played REAL, stats TEXT, expert_note REAL);
CREATE TABLE IF NOT EXISTS evaluations(id INTEGER PRIMARY KEY, goalkeeper_id TEXT, inputs TEXT, versions TEXT, output TEXT, comment TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS ab_tests(id INTEGER PRIMARY KEY, rulebase TEXT, version_a INT, version_b INT, results TEXT, created TEXT);
"""

def init():
    c = conn(); c.executescript(SCHEMA)
    if not c.execute("SELECT 1 FROM variable_versions").fetchone():
        vs = yaml.safe_load((SEED / "variables.yaml").read_text(encoding="utf-8"))["variables"]
        c.execute("INSERT INTO variable_versions(version,data,author,comment,created,active) VALUES(1,?,?,?,?,1)",
                  (json.dumps(vs, ensure_ascii=False), "seed", "version initiale", now()))
        for f in sorted((SEED / "rulebases").glob("*.yaml")):
            y = yaml.safe_load(f.read_text(encoding="utf-8"))
            c.execute("INSERT INTO rulebase_versions(rulebase,version,rules,gen,author,comment,created,active) VALUES(?,?,?,?,?,?,?,1)",
                      (y["rule_base"], 1, json.dumps(y["rules"], ensure_ascii=False), json.dumps(y.get("gen", {})), "seed", "base générée", now()))
        fx = ROOT / "data/fixtures/goalkeepers/goalkeepers.csv"
        if fx.exists():
            for r in csv.DictReader(open(fx, encoding="utf-8")):
                st = {k: float(v) for k, v in r.items() if k not in META and k not in ("age", "minutes_played", "league_visibility")}
                c.execute("INSERT OR IGNORE INTO goalkeepers VALUES(?,?,?,?,?,?,?,?)", (r["id"], r["name"], r["club"], float(r["age"]),
                          float(r["league_visibility"]), float(r["minutes_played"]), json.dumps(st), float(r["expert_note"])))
    c.commit(); c.close()
