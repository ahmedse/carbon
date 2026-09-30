"""K6 coverage. A named course cites 95 verbatim sentences or it is not at the bar."""
from pathlib import Path

import yaml

from ai.moodle_bank import MISS, cite_open_activity, load_c3, load_c4_files

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold"
_COURSES = _GOLD / "courses"
_ASK = "According to the handout"
_FULL = (
    "NMD1000",
    "NMD1301",
    "NMD1402",
    "NMD2101",
    "MED213",
    "NMD2303",
    "NMD2403",
    "NMD3101",
    "NMD3304",
    "NMD4201",
    "MED520",
    "MED5310",
)


def _load(shortname: str) -> dict:
    return yaml.safe_load((_COURSES / f"{shortname}.yaml").read_text(encoding="utf-8"))


def _bank(shortname: str) -> dict:
    return {**load_c3(shortname), **load_c4_files(shortname)}


def _cases(shortname: str) -> tuple[list, list]:
    extra = _load(shortname)
    if shortname != "NMD1103":
        return extra["hits"], extra["misses"]
    base = yaml.safe_load((_GOLD / "c6.yaml").read_text(encoding="utf-8"))
    return base["hits"] + extra["hits"], base["misses"] + extra["misses"]


def test_every_named_course_cites_95():
    for shortname in (*_FULL, "NMD1103"):
        hits, misses = _cases(shortname)
        assert len(hits) == 95, shortname
        assert len(misses) == 5, shortname
        assert len({case["quote"] for case in hits}) == 95, shortname
        bank = _bank(shortname)
        for case in hits:
            assert case["quote"] in bank[case["passage"]]["text"]
            owners = [row["id"] for row in bank.values() if case["quote"] in row["text"]]
            assert owners == [case["passage"]], shortname
            answer = cite_open_activity(
                f"{_ASK}, {case['quote']}",
                bank,
                course=shortname,
                activity_id=case["activity"],
                world="aast-mbbs",
            )
            assert answer.startswith(case["passage"] + "\n"), shortname
            assert case["quote"] in answer
        for case in misses:
            answer = cite_open_activity(
                f"{_ASK}, {case['quote']}",
                bank,
                course=shortname,
                activity_id=case["activity"],
                world="aast-mbbs",
            )
            assert answer == MISS, shortname
            if case.get("absent"):
                assert case["absent"] not in answer
