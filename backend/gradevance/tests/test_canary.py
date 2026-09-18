from gradevance.services.canary import evaluate_canary


def test_canary_blocks_small_held_out():
    r = evaluate_canary(expert_labels=["A"], engine_labels=["A"], held_out_n=1)
    assert r.allowed is False


def test_canary_passes_with_kappa():
    labels = ["SG+", "SG-", "SG--", "SG+", "SG-", "SG++"]
    r = evaluate_canary(
        expert_labels=labels,
        engine_labels=labels,
        held_out_n=len(labels),
        minimum_kappa=0.6,
    )
    assert r.allowed is True
    assert "new runs only" in r.reason
