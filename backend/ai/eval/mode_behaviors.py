"""Observable Pulse behaviors for Ask, Plan, and Tasks.

This is the contract. A sentence that is not a row here is not a new product.
A miss on a row is a failed behavior. Scores on the Ask board and the Plan &
Tasks board do not move because this list exists.

``proof``:
  locked — ``ai/tests/test_mode_behaviors.py`` fails if the row breaks.
  live   — only a dated run can show it. This file does not claim it.
  open   — the bar. Not locked by this bank yet.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Behavior:
    id: str
    mode: str
    when: str
    must: str
    must_not: str
    proof: str

    def as_dict(self) -> dict:
        return asdict(self)


BEHAVIORS: tuple[Behavior, ...] = (
    # ── Ask ──────────────────────────────────────────────────────────────
    Behavior(
        "ASK-01", "ask",
        "The user asks one read, such as “What is my leave balance?”",
        "Answer from that read. No plan card.",
        "Do not show Create task. A one-step read is not a task.",
        "locked",
    ),
    Behavior(
        "ASK-02", "ask",
        "Ask is about to draft a reply.",
        "The tool list has no plan_task, edit_plan, or approve_plan.",
        "Do not offer a tool that stores, edits, or approves a task.",
        "locked",
    ),
    Behavior(
        "ASK-03", "ask",
        "The user asks Ask to submit a change, such as leave.",
        "Hand off to Plan or to My. Say Ask does not create tasks.",
        "Do not say the change was submitted. The host record stays unchanged.",
        "locked",
    ),
    Behavior(
        "ASK-04", "ask",
        "A host write is the user’s intent on Ask.",
        "plan_task, edit_plan, and approve_plan are mutations and are cancelled.",
        "Do not show Confirm for that write because Agent mode is off.",
        "locked",
    ),
    Behavior(
        "ASK-05", "ask",
        "After a leave clarification, the user says “Make it 2 days.”",
        "Keep the leave type and the start date, then hand the write off.",
        "Do not submit the leave.",
        "live",
    ),
    Behavior(
        "ASK-06", "ask",
        "The user asks “Who am I?”",
        "Answer with this login’s name and employee number from the host.",
        "Do not answer with another employee’s row.",
        "live",
    ),
    Behavior(
        "ASK-07", "ask",
        "The answer states a number.",
        "That number appears in the tool payload for this turn.",
        "Do not invent a salary, a balance, a count, or a title.",
        "live",
    ),
    Behavior(
        "ASK-08", "ask",
        "The user asks for department and manager, and does not name pay.",
        "Answer with department and manager only.",
        "Do not print basic salary.",
        "live",
    ),
    Behavior(
        "ASK-09", "ask",
        "The user asks for a limit the balance read already returned, such as sick entitled.",
        "State that figure from the read.",
        "Do not answer “ask HR” when the figure was in the payload.",
        "live",
    ),
    Behavior(
        "ASK-10", "ask",
        "The user asks for a person or a figure this login cannot see.",
        "Say the read was refused.",
        "Do not invent the figure. Do not grant people:view to make the case pass.",
        "locked",
    ),
    Behavior(
        "ASK-11", "ask",
        "The user says “the same count” or otherwise points at the last result.",
        "Resolve it from ConversationState (open question, slots, last results).",
        "Do not start a new search because the words look like a fresh topic.",
        "live",
    ),
    Behavior(
        "ASK-12", "ask",
        "The user writes in Arabic.",
        "Answer in Arabic. Quote host values as stored.",
        "Do not answer the Arabic question in English.",
        "live",
    ),
    Behavior(
        "ASK-13", "ask",
        "Any Ask turn ends.",
        "Log one TurnDecision.",
        "Do not log two competing exits for the same turn.",
        "live",
    ),
    Behavior(
        "ASK-14", "ask",
        "The user states a fact worth remembering.",
        "Ask them to confirm. Store it only after that confirm.",
        "Do not write memory, or anything else, without that confirm.",
        "locked",
    ),
    Behavior(
        "ASK-15", "ask",
        "A Plan draft exists in another session.",
        "Ask stays an answer. It does not treat that draft as approved.",
        "Do not call edit_plan or approve_plan.",
        "locked",
    ),
    Behavior(
        "ASK-16", "ask",
        "The 19-turn Ask bank runs.",
        "At most 2 turns take longer than 4 seconds.",
        "Do not sign a latency pass while 4 or more turns are over 4 seconds.",
        "live",
    ),
    # ── Plan ─────────────────────────────────────────────────────────────
    Behavior(
        "PLAN-01", "plan",
        "On Plan: “Create a 1-step task that lists my direct reports then stops. Do not write.”",
        "Show one read step, api list_my_direct_reports, effect read, empty plan id. Say no task exists until Create task.",
        "Do not store a task. Do not approve it. Do not run it.",
        "locked",
    ),
    Behavior(
        "PLAN-02", "plan",
        "The same one-step read is judged without the Plan flag.",
        "is_task_plan stays false. Ask still gets an answer, not a card.",
        "Do not turn every one-step read in Ask into a task.",
        "locked",
    ),
    Behavior(
        "PLAN-03", "plan",
        "The proposal card is on screen.",
        "plan_id is empty. The task row appears only after Create task, as pending_approval.",
        "Do not treat the card, or opening Tasks, as approval.",
        "locked",
    ),
    Behavior(
        "PLAN-04", "plan",
        "The user presses Create task.",
        "POST /ai/plans/proposal/commit/ stores the plan they reviewed.",
        "Do not store a different plan than the card showed.",
        "live",
    ),
    Behavior(
        "PLAN-05", "plan",
        "The user is looking at the Plan card.",
        "The actions are Create task, Change, and Cancel.",
        "Do not put Approve or Run on the Plan card.",
        "locked",
    ),
    Behavior(
        "PLAN-06", "plan",
        "The user types in the composer while a draft is open.",
        "Stay on this draft, unless they used Change.",
        "Do not re-plan from composer text. Change is the only revision, and it sends plan_change.",
        "locked",
    ),
    Behavior(
        "PLAN-07", "plan",
        "With a draft open, the user asks “why you approved it?!”",
        "Keep the same steps. Say nothing has been approved and nothing is stored.",
        "Do not start a new plan that searches for an approval.",
        "locked",
    ),
    Behavior(
        "PLAN-08", "plan",
        "With an unstored draft open, the user says “cancel” or “i said cancel”.",
        "Drop the draft. Say the draft is dropped and nothing was stored. The card goes away.",
        "Do not answer again with “still waiting for Create task”.",
        "locked",
    ),
    Behavior(
        "PLAN-09", "plan",
        "The user already pressed Create task, then says cancel in Plan.",
        "Cancel drops only an open unstored draft. The created task stays in Tasks until the user acts there.",
        "Do not delete a pending_approval task from a Plan composer cancel.",
        "locked",
    ),
    Behavior(
        "PLAN-10", "plan",
        "Plan blocks a tool that would approve or edit.",
        "The headline is “Nothing is approved yet”.",
        "Do not say “Plans are approved in Agent”.",
        "locked",
    ),
    Behavior(
        "PLAN-11", "plan",
        "Plan is about to draft.",
        "Withhold edit_plan, approve_plan, plan_task, and live host reads.",
        "Do not let the draft model approve the plan or answer the brief by calling the host.",
        "locked",
    ),
    Behavior(
        "PLAN-12", "plan",
        "The card lists steps.",
        "Each step shows intent, whether it reads or changes, and the api name. A blocked step shows why. Create stays off when the catalog cannot produce the deliverable.",
        "Do not hide a write inside a step marked as a read.",
        "locked",
    ),
    Behavior(
        "PLAN-13", "plan",
        "The user is in a Plan thread.",
        "The footer says this thread drafts a plan, Ask is a separate session, and nothing runs until Approve.",
        "Do not say the plan is already running.",
        "locked",
    ),
    Behavior(
        "PLAN-14", "plan",
        "The planner returns one step that changes data.",
        "That step is a proposal even without the one-read flag. It is still not stored or run.",
        "Do not run the write from Plan.",
        "locked",
    ),
    # ── Tasks ────────────────────────────────────────────────────────────
    Behavior(
        "TASK-01", "task",
        "The user opens Tasks on a card they have not created.",
        "No task. After Create, status is pending_approval.",
        "Do not mark it approved because the panel opened.",
        "live",
    ),
    Behavior(
        "TASK-02", "task",
        "The task is pending_approval.",
        "Approve is a separate act. Run stays unavailable until Approve.",
        "Do not start the run from Approve alone, or from opening the row.",
        "locked",
    ),
    Behavior(
        "TASK-03", "task",
        "Run reaches a step.",
        "A step that changes data pauses for that step’s confirm before the host call. A read does not pause again after Run.",
        "Do not call the host write before that confirm.",
        "locked",
    ),
    Behavior(
        "TASK-04", "task",
        "get_my_profile returns an employee number that is not the run owner.",
        "Fail that step and the leave-balance step. Name the owner number and the result number.",
        "Do not complete the run. Direct reports are not part of this check.",
        "locked",
    ),
    Behavior(
        "TASK-05", "task",
        "A read step finishes with a host body and an empty draft.",
        "Show the body, or fail the step. A finished run with the empty-plan sentence becomes failed.",
        "Do not say “I wasn't able to complete the requested plan” on a completed run.",
        "locked",
    ),
    Behavior(
        "TASK-06", "task",
        "emp_1067 runs profile, then leave.",
        "The result is that user’s name, employee number, and leave figures.",
        "Do not state another employee’s identity on that run.",
        "live",
    ),
    Behavior(
        "TASK-07", "task",
        "emp_1712 runs a one-step direct-reports task.",
        "The table is that manager’s reports: employee number, name, job title.",
        "Do not include pay columns. Do not finish with an empty draft.",
        "live",
    ),
    Behavior(
        "TASK-08", "task",
        "emp_2378 runs profile, then leave.",
        "The result is that user’s name and employee number.",
        "Do not state the My user’s identity on the HR user’s run.",
        "live",
    ),
    Behavior(
        "TASK-09", "task",
        "The host returns 403.",
        "The result says the read was refused.",
        "Do not fill in the forbidden figure.",
        "live",
    ),
    Behavior(
        "TASK-10", "task",
        "The run is in progress.",
        "Now names the step the user asked for.",
        "Do not collapse two different reads into one internal label.",
        "live",
    ),
    Behavior(
        "TASK-11", "task",
        "The run completes.",
        "“Finished. Here’s what I found.” only when the result shows the host data.",
        "Do not use that sentence over an empty draft.",
        "locked",
    ),
    Behavior(
        "TASK-12", "task",
        "A step fails.",
        "The run stays failed and names the blocked step and a next action.",
        "Do not mark the run completed.",
        "locked",
    ),
    Behavior(
        "TASK-13", "task",
        "The user wants a host change.",
        "The host is called only after Approve, Run, and the step confirm.",
        "Chat and Plan must not say the change was submitted.",
        "locked",
    ),
    Behavior(
        "TASK-14", "task",
        "The user discusses a task in Ask or Plan.",
        "The reply stays talk, or a new unstored draft.",
        "Do not edit or approve the stored task from that message.",
        "locked",
    ),
    Behavior(
        "TASK-15", "task",
        "The user retries a run.",
        "A write that already committed is not sent again.",
        "Do not strip the mutation flag so a retry skips confirm.",
        "locked",
    ),
    Behavior(
        "TASK-16", "task",
        "A later bench passes.",
        "Night 2026-09-23 FAIL stays on the board.",
        "Do not clear that night because a newer run passed.",
        "locked",
    ),
    Behavior(
        "TASK-17", "task",
        "Someone asks if Tasks is ready to go live.",
        "Ready only when every production row is reached on dated evidence.",
        "A lab 10/10 does not close go-live. Ask’s score does not close it either.",
        "locked",
    ),
)


def by_id() -> dict[str, Behavior]:
    return {row.id: row for row in BEHAVIORS}


def counts() -> dict[str, int]:
    return {
        "all": len(BEHAVIORS),
        "ask": sum(1 for row in BEHAVIORS if row.mode == "ask"),
        "plan": sum(1 for row in BEHAVIORS if row.mode == "plan"),
        "task": sum(1 for row in BEHAVIORS if row.mode == "task"),
        "locked": sum(1 for row in BEHAVIORS if row.proof == "locked"),
        "live": sum(1 for row in BEHAVIORS if row.proof == "live"),
        "open": sum(1 for row in BEHAVIORS if row.proof == "open"),
    }
