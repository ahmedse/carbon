"""K6 file banks. A span is copied from the open file. No authored question."""
from ai.moodle_bank import MISS, cite_open_activity, load_c4_files

_JOINED = (
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
_WORLD = "aast-mbbs"


def _span(text: str) -> str:
    start = min(80, max(0, len(text) - 48))
    return text[start : start + 48]


def test_a_span_from_the_open_file_cites_that_file():
    for shortname in _JOINED:
        bank = load_c4_files(shortname)
        assert bank, shortname
        row = next(iter(bank.values()))
        span = _span(row["text"])
        assert len(span) >= 24
        assert span in row["text"]
        answer = cite_open_activity(
            f"According to the handout, {span}",
            bank,
            course=shortname,
            activity_id=row["activity_id"],
            world=_WORLD,
        )
        assert answer.startswith(row["id"] + "\n"), shortname
        assert span in answer


def test_a_span_from_another_course_is_the_lecture_miss():
    banks = {shortname: load_c4_files(shortname) for shortname in _JOINED}
    donor = next(iter(banks["NMD1000"].values()))
    span = _span(donor["text"])
    for shortname in _JOINED:
        if shortname == "NMD1000":
            continue
        row = next(iter(banks[shortname].values()))
        assert span not in row["text"]
        answer = cite_open_activity(
            f"According to the handout, {span}",
            banks[shortname],
            course=shortname,
            activity_id=row["activity_id"],
            world=_WORLD,
        )
        assert answer == MISS, shortname


def test_an_unlisted_course_has_no_file_bank():
    assert load_c4_files("NMD1601") == {}
