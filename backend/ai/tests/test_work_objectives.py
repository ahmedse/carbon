"""Phase 3 — WorkObjective durable work item."""
import pytest

pytestmark = pytest.mark.django_db(transaction=True)


def _make_ctx(instance_id="i1", host_user_id="u1", conversation_id="c1"):
    from ai.engine.agent.plugins import ToolContext
    return ToolContext(
        instance_id=instance_id,
        host_user_id=host_user_id,
        conversation_id=conversation_id,
    )


@pytest.mark.asyncio
async def test_save_work_objective_creates_row():
    """save_work_objective must create a WorkObjective row and return its id."""
    from asgiref.sync import sync_to_async

    from ai.plugins.save_work_objective import SaveWorkObjective

    ctx = _make_ctx()
    result = await SaveWorkObjective().execute({
        "title": "Investigate emissions change",
        "description": "Find why Scope 2 emissions increased 15% in August",
        "progress_so_far": "Found that electricity consumption increased",
        "remaining_work": "Need to check if the emission factor changed",
    }, ctx=ctx)

    assert result["status"] == "saved"
    assert "objective_id" in result
    assert result["title"] == "Investigate emissions change"

    from ai.models.core import WorkObjective
    obj = await sync_to_async(WorkObjective.objects.get, thread_sensitive=True)(
        id=result["objective_id"]
    )
    assert obj.status == "open"
    assert obj.host_user_id == "u1"
    assert "Found so far" in obj.latest_summary


@pytest.mark.asyncio
async def test_get_work_objectives_returns_open_items():
    """get_work_objectives must return previously saved objectives."""
    from ai.plugins.save_work_objective import SaveWorkObjective
    from ai.plugins.get_work_objectives import GetWorkObjectives

    ctx = _make_ctx()
    await SaveWorkObjective().execute({
        "title": "DQ audit",
        "description": "Audit null rates in the people module",
        "progress_so_far": "Found 3 tables with >5% nulls",
        "remaining_work": "Need to propose DQ rules for each",
    }, ctx=ctx)

    result = await GetWorkObjectives().execute({"status_filter": "open"}, ctx=ctx)

    assert result["status"] == "resolved"
    assert result["count"] >= 1
    titles = [o["title"] for o in result["objectives"]]
    assert "DQ audit" in titles


@pytest.mark.asyncio
async def test_get_work_objectives_returns_no_match_when_empty():
    """get_work_objectives must return no_match status when no objectives exist."""
    from ai.plugins.get_work_objectives import GetWorkObjectives

    ctx = _make_ctx(host_user_id="user_with_no_objectives")
    result = await GetWorkObjectives().execute({"status_filter": "open"}, ctx=ctx)

    assert result["status"] == "no_match"
    assert "hint" in result


@pytest.mark.asyncio
async def test_save_objective_requires_title():
    """save_work_objective must return error when title is missing."""
    from ai.plugins.save_work_objective import SaveWorkObjective

    ctx = _make_ctx()
    result = await SaveWorkObjective().execute({
        "title": "",
        "description": "Something",
        "progress_so_far": "",
        "remaining_work": "everything",
    }, ctx=ctx)

    assert result["status"] == "error"
