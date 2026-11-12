import csv, pathlib, pytest
from scouting_engine import Model
ROOT = pathlib.Path(__file__).resolve().parents[1]

@pytest.fixture(scope="session")
def gk(): return Model.from_dir(ROOT / "data/seed/goalkeeper")
@pytest.fixture(scope="session")
def lat(): return Model.from_dir(ROOT / "data/seed/lateral")
@pytest.fixture(scope="session")
def gk_rows():
    rows = list(csv.DictReader(open(ROOT / "data/fixtures/goalkeepers/goalkeepers.csv", encoding="utf-8")))
    return [{k: (float(v) if k not in ("id", "name", "archetype", "club") else v) for k, v in r.items()} for r in rows]
