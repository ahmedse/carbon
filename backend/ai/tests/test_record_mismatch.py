"""A path-keyed read must return the record the user identified."""
from ai.engine.cognition.turn.pipeline_v21 import mismatched_reads
from ai.protocol import turn_meter_from_result


def _keys(name):
    return {"id"} if name == "get_employee" else set()


def _row(path_id, result):
    return {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "get_employee", "path_params": {"id": path_id}},
        "result": result,
    }


def test_a_different_record_is_a_mismatch():
    caller = {"status_code": 200, "data": {"id": 17, "employee_no": "2378", "full_name": "Ali"}}
    out = mismatched_reads([_row(17, caller)], user_message="Employee number 2400", path_keys=_keys)
    assert [r["name"] for r in out] == ["get_employee"]
    assert "2400" in out[0]["detail"]


def test_a_not_found_path_value_is_a_mismatch():
    missing = {"status_code": 404, "data": {"detail": "No Employee matches the given query."}}
    out = mismatched_reads([_row(2400, missing)], user_message="Employee number 2400", path_keys=_keys)
    assert out and "no record has that path value" in out[0]["detail"]


def test_the_named_record_is_not_a_mismatch():
    named = {"status_code": 200, "data": {"id": 267, "employee_no": "2400", "full_name": "Abdullah"}}
    assert mismatched_reads([_row(267, named)], user_message="Employee number 2400", path_keys=_keys) == []


def test_no_identifier_in_the_message_checks_nothing():
    caller = {"status_code": 200, "data": {"id": 17, "employee_no": "2378"}}
    assert mismatched_reads([_row(17, caller)], user_message="Tell me about him", path_keys=_keys) == []


def test_reads_without_a_path_key_are_not_checked():
    row = {"tool_args": {"api_name": "list_employees"}, "result": {"status_code": 200, "data": {"count": 555}}}
    assert mismatched_reads([row], user_message="Employee number 2400", path_keys=_keys) == []


def test_turn_meter_keeps_only_turn_facts():
    meter = turn_meter_from_result({
        "content": "x", "llm_calls": 1, "llm_calls_by_stage": {"understand": 1},
        "turn_decision": "tool_answer", "truthfulness_flags": [],
    })
    assert meter == {
        "turn_decision": "tool_answer", "llm_calls": 1,
        "llm_calls_by_stage": {"understand": 1}, "truthfulness_flags": [],
    }
    assert turn_meter_from_result(None) is None
