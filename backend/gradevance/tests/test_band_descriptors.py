"""Band descriptors present for draft multi-domain rubrics."""
from gradevance.services.packs import load_rubric


def test_cbl_band_descriptors_filled():
    rub = load_rubric("engines/rubric/medicine_cbl_analytic_v1")
    bands = (rub.band_descriptors or {}).get("criterion_bands") or {}
    assert "differential_diagnosis" in bands
    assert "Excellent" in bands["differential_diagnosis"]


def test_article_band_descriptors_filled():
    rub = load_rubric("engines/rubric/article_analytic_generic_v1")
    bands = (rub.band_descriptors or {}).get("criterion_bands") or {}
    assert "argument_structure" in bands
    assert "A" in bands["argument_structure"]


def test_ospe_band_descriptors_filled():
    rub = load_rubric("engines/rubric/medicine_ospe_urinalysis_v1")
    bands = (rub.band_descriptors or {}).get("criterion_bands") or {}
    assert "interpretation" in bands
