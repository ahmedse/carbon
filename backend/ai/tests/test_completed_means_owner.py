"""A completed read belongs to the run owner and shows the host body."""
from ai.engine.cognition.plan.export_bind import show_or_fail_read
from ai.engine.cognition.plan.loop import StepResult, downgrade_empty_completion
from ai.plans_service import apply_self_read_owner


class _Step:
    def __init__(self, api, output, status="completed"):
        self.status = status
        self.error = ""
        self.tool_args_json = {"api_name": api}
        self.tool_output_json = output
        self.saved = []

    def save(self, **kwargs):
        self.saved.append(kwargs.get("update_fields"))


class _Run:
    def __init__(self):
        self.status = "completed"
        self.host_user_id = "13"
        self.final_response = "Ali Mohamed Saad AlAjmi"
        self.saved = []

    def save(self, **kwargs):
        self.saved.append(kwargs.get("update_fields"))


def _profile(employee_no):
    return {
        "result": {
            "status_code": 200,
            "data": {"employee_no": employee_no, "full_name": "x"},
        }
    }


def test_foreign_self_profile_fails_the_run_and_its_leave_step():
    run = _Run()
    profile = _Step("get_my_profile", _profile("2378"))
    leave = _Step("get_my_leave_balance", {"result": {"status_code": 200, "data": []}})
    reports = _Step("list_my_direct_reports", _profile("1067"))
    assert apply_self_read_owner(run, [profile, leave, reports], "1067") is True
    assert run.status == "failed"
    assert "1067" in run.final_response
    assert "2378" in run.final_response
    assert profile.status == "failed"
    assert leave.status == "failed"
    assert reports.status == "completed"


def test_owner_self_profile_stays_completed():
    run = _Run()
    profile = _Step("get_my_profile", _profile("1067"))
    assert apply_self_read_owner(run, [profile], "1067") is False
    assert run.status == "completed"
    assert profile.status == "completed"


_REPORTS = {
    "name": "list_my_direct_reports",
    "kind": "read",
    "empty_render": "no_direct_reports",
    "returns": ["employee_no", "full_name"],
    "field_labels": {
        "employee_no": {"en": "Employee number"},
        "full_name": {"en": "Name"},
    },
}


def test_empty_draft_with_a_host_body_is_shown():
    result = StepResult(
        step_id=0,
        intent="list reports",
        tool_output={
            "result": {
                "status_code": 200,
                "data": [{"employee_no": "1067", "full_name": "Bilagot Panta Suerte"}],
            }
        },
    )
    show_or_fail_read(
        result,
        {"api_name": "list_my_direct_reports"},
        language="en",
        catalog=[_REPORTS],
        is_mutation=False,
    )
    assert result.error is None
    assert "1067" in result.draft_text
    assert "Bilagot Panta Suerte" in result.draft_text


def test_empty_draft_that_cannot_be_shown_fails():
    result = StepResult(
        step_id=0,
        intent="read",
        tool_output={"result": {"status_code": 200, "data": [{"employee_no": "1067"}]}},
    )
    show_or_fail_read(
        result,
        {"api_name": "unnamed_read"},
        language="en",
        catalog=[],
        is_mutation=False,
    )
    assert result.error
    assert result.critic_verdict == "veto"


def test_empty_completion_sentence_is_a_failure():
    status, succeeded = downgrade_empty_completion(
        "completed",
        "I wasn't able to complete the requested plan. Some steps encountered errors.",
        [StepResult(step_id=0, intent="list reports")],
        True,
    )
    assert status == "failed"
    assert succeeded is False


def test_rendered_owner_profile_is_left_alone():
    result = StepResult(
        step_id=0,
        intent="profile",
        draft_text="Bilagot Panta Suerte",
        tool_output=_profile("1067"),
    )
    show_or_fail_read(
        result,
        {"api_name": "get_my_profile"},
        language="en",
        catalog=[],
        is_mutation=False,
    )
    assert result.draft_text == "Bilagot Panta Suerte"
    assert result.error is None
