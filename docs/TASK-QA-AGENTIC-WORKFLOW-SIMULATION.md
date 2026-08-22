# TASK-QA-AGENTIC-WORKFLOW-SIMULATION
# QA Test: Multi-Agent Orchestration Lifecycle (Complex Task Scenario)

**Role:** QA/Validator (evidence-only — validate behavior, not fix code)  
**Model:** DeepSeek V4-Flash  
**Domain:** Pulse agentic task orchestration (Sprint 23 W3-A/B/C/F + next-gen extensions)  
**Task ID:** QA-AGENTIC-WORKFLOW-SIMULATION  
**Parent:** AI Workspace track + Task Panel (`AITaskPanel.jsx`, plans API, plans service)  
**Goal:** Validate Pulse's capability to handle sophisticated multi-agent workflows using a realistic complex scenario as the test case.

---

## Test Scenario: Create Platform Documentation (Word + Excel)

### User Request (test input)
```
"I want you to create Word and Excel files that are the detailed documentation 
guide of the Data Trust platform. Let's discuss."
```

### Expected Pulse Behavior (ideal multi-agent orchestration)

#### Phase 1: Intent Recognition & Reasoning
**What SHOULD happen:**
- Pulse recognizes this is NOT a primitive tool-call task
- Engages in discovery conversation to understand scope:
  - "What aspects of the platform should the documentation cover?"
  - "Who is the target audience (users, admins, developers)?"
  - "Should it include API reference, user guides, architecture diagrams?"
  - "Any specific sections or structure you prefer?"
- Infers this requires multiple specialized agents:
  - Content researcher (gather platform info)
  - Documentation writer (structure + compose)
  - Diagram generator (architecture visuals)
  - Format specialist (Word/Excel output)

#### Phase 2: Plan Proposal
**What SHOULD happen:**
- Pulse proposes a structured multi-agent plan:
  ```
  WORKFLOW: Platform Documentation Generation
  
  Phase 1: Discovery & Analysis
    - Agent: researcher
    - Steps:
      1. Audit codebase structure (backend/frontend/docs)
      2. Extract API endpoints and models
      3. Identify key features and user journeys
      4. Gather existing documentation fragments
    - Outputs: structured content inventory
  
  Phase 2: Documentation Architecture
    - Agent: documentation-architect
    - Steps:
      1. Define document structure (TOC, sections)
      2. Map content to sections
      3. Identify diagram requirements
      4. Define Excel workbook structure (sheets, tables)
    - Outputs: documentation blueprint
  
  Phase 3: Content Generation
    - Agent: content-writer (parallel tasks)
    - Steps:
      1. Write Executive Overview
      2. Write Platform Architecture section
      3. Write User Guide sections
      4. Write API Reference
      5. Write Admin Guide
    - Outputs: draft content sections
  
  Phase 4: Diagram & Visual Assets
    - Agent: diagram-generator
    - Steps:
      1. Create architecture diagram (Mermaid)
      2. Create data flow diagrams
      3. Create UI mockups/screenshots
    - Outputs: diagram files
  
  Phase 5: Format & Assembly
    - Agent: document-assembler
    - Steps:
      1. Assemble Word document with formatting
      2. Create Excel workbook with matrices/glossary
      3. Embed diagrams
      4. Apply styling and TOC
    - Outputs: final Word + Excel files
  
  Phase 6: Review & Delivery
    - Agent: quality-reviewer
    - Steps:
      1. Validate completeness
      2. Check formatting consistency
      3. Verify links and references
    - Outputs: validated deliverables
  
  Expected duration: 15-20 minutes
  Requires approval: Yes (before Phase 3 content generation)
  ```

- User can review, tune, or approve the plan
- User can modify:
  - Add/remove phases
  - Change agent assignments
  - Adjust step details
  - Set approval gates

#### Phase 3: Schedule & Trigger
**What SHOULD happen:**
- User says: "Create and schedule this task"
- Pulse creates a durable plan record with `status=pending_approval`
- Plan is visible in Tasks panel
- User approves the plan → `status=approved`
- User clicks "Run" → execution begins

#### Phase 4: Execution & Monitoring
**What SHOULD happen:**
- Execution starts, live status visible:
  ```
  ⏳ Phase 1: Discovery & Analysis (running)
     ✓ Step 1: Audit codebase structure (completed - 45s)
     ⏳ Step 2: Extract API endpoints (running...)
     ⏸ Step 3: Identify key features (pending)
     ⏸ Step 4: Gather documentation (pending)
  ```
- Real-time progress updates:
  - Step status badges
  - Output summaries (not raw JSON)
  - Logs available on demand
  - Metrics visible (latency, tokens, cost)
- User can see intermediate outputs:
  - "Found 127 API endpoints"
  - "Identified 8 major features"
  - "Collected 23 existing doc fragments"

#### Phase 5: User Control Actions
**What SHOULD happen:**
- User can pause at any time → execution stops gracefully
- User can resume → picks up from last completed step
- User can stop → cancels remaining work, preserves completed artifacts
- User can modify mid-execution:
  - Edit a step's parameters
  - Skip a step
  - Add a new step
  - Change agent for remaining work

#### Phase 6: Approval Gates
**What SHOULD happen:**
- Phase 3 (content generation) requires approval before writing
- Execution pauses:
  ```
  ⏸ Phase 3: Content Generation
     ⚠ This phase will generate 5 large content sections.
     Preview:
       - Executive Overview (est. 2 pages)
       - Platform Architecture (est. 8 pages)
       - User Guide (est. 15 pages)
       - API Reference (est. 12 pages)
       - Admin Guide (est. 10 pages)
     
     [Approve] [Modify] [Skip]
  ```
- User approves → execution continues
- User modifies → opens edit dialog, then re-approves
- User skips → that phase is marked skipped, moves to next

#### Phase 7: Results & Outputs
**What SHOULD happen:**
- Upon completion:
  ```
  ✓ Documentation Generation Complete
  
  Deliverables:
    📄 Data_Trust_Platform_Guide.docx (47 pages, 12.3 MB)
       - Executive Overview
       - Platform Architecture (with diagrams)
       - User Guide
       - API Reference
       - Admin Guide
       - Appendices
    
    📊 Data_Trust_Platform_Workbook.xlsx (8 sheets)
       - Glossary
       - API Endpoints Matrix
       - Roles & Responsibilities
       - Feature Comparison
       - Configuration Reference
       - Troubleshooting Checklist
       - Compliance Matrix
       - Metrics & KPIs
    
  Metrics:
    Duration: 18m 32s
    Tokens: 125,430
    Cost: $0.42
    Approvals: 2
    Steps: 24 total (23 completed, 1 skipped)
  
  [Download Word] [Download Excel] [View Audit Ledger]
  ```
- Files are downloadable artifacts
- Audit ledger shows full provenance
- User can rerun with modifications
- User can fork into a variant

#### Phase 8: Audit & Observability
**What SHOULD happen:**
- Full audit trail available:
  - Who requested (user)
  - When (timestamps)
  - What plan was approved
  - Which agents executed which steps
  - What outputs were generated
  - What approvals were given
  - Resource usage (tokens, cost, latency)
  - Any errors or retries
- Observable timeline:
  ```
  18:32:15 | Plan created | User: ahmed
  18:33:02 | Plan approved | User: ahmed
  18:33:05 | Phase 1 started | Agent: researcher
  18:33:50 | Step 1 completed | Output: 127 endpoints
  18:34:15 | Step 2 completed | Output: 8 features
  ...
  18:45:20 | Phase 3 paused | Reason: awaiting approval
  18:46:10 | Phase 3 approved | User: ahmed
  18:46:12 | Phase 3 resumed
  ...
  18:51:37 | All phases completed | Status: success
  ```

---

## Validation Criteria (What to Test)

### V1: Intent Recognition
- [ ] Pulse identifies this as a complex multi-agent task
- [ ] Pulse does NOT immediately call `export_document` tool
- [ ] Pulse engages in discovery conversation
- [ ] Pulse asks clarifying questions about scope/audience/structure

### V2: Plan Quality
- [ ] Generated plan has clear phases
- [ ] Each phase has agent assignment
- [ ] Steps are specific and actionable
- [ ] Dependencies are identified
- [ ] Expected outputs are defined
- [ ] Duration estimate is reasonable
- [ ] Approval gates are specified

### V3: User Tuning
- [ ] User can review plan before approval
- [ ] User can modify phases, steps, agents
- [ ] User can add/remove approval gates
- [ ] Changes trigger re-approval flow
- [ ] Diff review shows what changed

### V4: Execution Control
- [ ] Plan status transitions correctly (pending→approved→running→paused→completed)
- [ ] Live status updates appear in real-time
- [ ] Step progress is visible
- [ ] User can pause execution
- [ ] User can resume from pause
- [ ] User can stop (cancel remaining work)
- [ ] Stop preserves completed artifacts

### V5: Monitoring & Progress
- [ ] Live execution graph shows current step
- [ ] Step cards show status, tool, output summary
- [ ] Logs are available per step
- [ ] Metrics update in real-time (tokens, latency, cost)
- [ ] No raw JSON dumps (semantic output only)
- [ ] Intermediate results are visible

### V6: Approval Gates
- [ ] Execution pauses at designated gates
- [ ] Preview shows what will happen next
- [ ] User can approve/modify/skip
- [ ] Modify opens step edit dialog
- [ ] Skip marks step as skipped
- [ ] Execution resumes after approval

### V7: Results Delivery
- [ ] Final outputs are structured artifacts (not JSON)
- [ ] Files are downloadable
- [ ] Output summary shows key metrics
- [ ] Audit ledger is accessible
- [ ] User can rerun the plan
- [ ] User can fork into a variant

### V8: Observability
- [ ] Full event timeline available
- [ ] Audit ledger shows provenance
- [ ] Resource usage is tracked
- [ ] Errors and retries are logged
- [ ] User actions are recorded (approvals, pauses, stops)

---

## Test Execution Plan

### Setup
1. Start Carbon platform (backend :8009, frontend :5179)
2. Login as `ahmed` (admin with AI access)
3. Open Pulse workspace
4. Verify task orchestration panel is available

### Test Steps

#### T1: Submit Complex Request
**Action:**  
- Send message: "I want you to create Word and Excel files that are the detailed documentation guide of the Data Trust platform. Let's discuss."

**Expected:**  
- Pulse recognizes complexity
- Asks clarifying questions
- Does NOT immediately generate files

**Validation:**  
- [ ] Response indicates multi-step approach
- [ ] Discovery questions appear
- [ ] No immediate tool execution

#### T2: Discovery Conversation
**Action:**  
- Answer Pulse's questions:
  - Scope: full platform (architecture, user guides, API, admin)
  - Audience: users + admins + developers
  - Structure: comprehensive with TOC, diagrams, matrices

**Expected:**  
- Pulse gathers requirements
- Proposes a multi-agent plan

**Validation:**  
- [ ] Pulse proposes structured plan
- [ ] Plan has multiple phases
- [ ] Agents are assigned to phases
- [ ] Expected outputs are defined

#### T3: Plan Review & Approval
**Action:**  
- Review proposed plan
- Request modification (e.g., "Add a troubleshooting section")
- Approve revised plan

**Expected:**  
- Plan is reviewable in Tasks panel
- Modifications trigger diff review
- Approval transitions plan to `approved` status

**Validation:**  
- [ ] Plan appears in Tasks panel with `pending_approval` status
- [ ] User can edit plan brief or steps
- [ ] Edits trigger diff review gate
- [ ] Approval changes status to `approved`

#### T4: Execute Plan
**Action:**  
- Click "Run" on approved plan

**Expected:**  
- Execution begins
- Live status updates appear
- Steps complete sequentially or in parallel

**Validation:**  
- [ ] Plan status → `running`
- [ ] Step cards appear with live status
- [ ] Progress indicators update
- [ ] Intermediate outputs are visible

#### T5: Monitor Execution
**Action:**  
- Watch live execution
- Open execution graph
- Check step logs

**Expected:**  
- Graph shows current progress
- Step statuses update
- Logs are accessible
- Metrics accumulate

**Validation:**  
- [ ] Live graph reflects current step
- [ ] Step status badges are accurate
- [ ] Logs show tool calls and outputs
- [ ] Token/cost metrics increment

#### T6: Pause & Resume
**Action:**  
- Click "Pause" during Phase 2
- Wait for pause confirmation
- Click "Resume"

**Expected:**  
- Execution pauses gracefully
- State is preserved
- Resume continues from pause point

**Validation:**  
- [ ] Plan status → `paused`
- [ ] In-flight step completes before pause
- [ ] Resume button appears
- [ ] Resume continues from correct step
- [ ] No steps are re-executed

#### T7: Approval Gate
**Action:**  
- Wait for Phase 3 approval gate
- Review preview
- Click "Approve"

**Expected:**  
- Execution pauses at gate
- Preview shows upcoming work
- Approval resumes execution

**Validation:**  
- [ ] Plan status → `paused` (awaiting approval)
- [ ] Step status → `awaiting_approval`
- [ ] Preview shows next actions
- [ ] Approve resumes execution
- [ ] Step status → `running`

#### T8: Results Delivery
**Action:**  
- Wait for completion
- Review final outputs

**Expected:**  
- Artifacts are available
- Summary shows metrics
- Files are downloadable

**Validation:**  
- [ ] Plan status → `completed`
- [ ] Artifacts card shows Word + Excel files
- [ ] Download links work
- [ ] File sizes and page counts are shown
- [ ] Metrics summary is accurate

#### T9: Audit Ledger
**Action:**  
- Open audit ledger

**Expected:**  
- Full provenance visible
- Timeline shows all events
- Resource usage is tracked

**Validation:**  
- [ ] Ledger shows plan creation timestamp
- [ ] All step executions are logged
- [ ] Approvals are recorded
- [ ] Token/cost accounting is complete
- [ ] User actions are tracked

#### T10: Rerun & Fork
**Action:**  
- Click "Rerun" on completed plan
- Click "Fork" to create variant

**Expected:**  
- Rerun creates new execution of same plan
- Fork creates editable copy

**Validation:**  
- [ ] Rerun preserves original plan
- [ ] New run has fresh status
- [ ] Fork creates new plan with `forked_from` link
- [ ] Fork is editable before approval

---

## Current Implementation Status (as of 2026-08-22)

### ✅ What EXISTS Today
- Plans API: create, list, approve, decline, run (SSE), confirm/decline step, stop, ledger
- Plans service: decompose via SkillAwarePlanner, execute via ReActLoop, durable Run/RunStep
- Frontend: AITaskPanel with Tasks/Run tabs, AITaskPlanCard, AITaskAuditCard
- Live plan DAG graph (PlanDagGraph + EnterpriseGraph)
- Step-level consent (RULE_21 approval gates)
- SSE streaming execution frames
- Audit ledger with provenance
- Phase/stage grouping in plan payload
- Stop/pause/resume controls (pause/resume API exists, frontend wired)
- Plan edit + diff review (W3-C)
- Fork plan (W3-C)

### ❌ What is MISSING (gaps for this scenario)

#### G1: Intent Recognition & Discovery
- **Gap:** No multi-turn discovery conversation before plan generation
- **Current:** User submits brief → immediate decomposition → plan
- **Needed:** Pulse should ask clarifying questions before proposing a plan

#### G2: Agent Assignment Visibility
- **Gap:** No visible agent role in plan preview (steps have `agent_role` but it's not prominent)
- **Current:** Steps show tool_name, but agent role is hidden or generic
- **Needed:** Each phase should clearly show which agent will execute it

#### G3: Multi-Agent Coordination Strategy
- **Gap:** No explicit multi-agent coordination semantics
- **Current:** Engine has one orchestrator, tool calls are sequential
- **Needed:** Support for parallel agent execution, agent handoffs, sub-workflows

#### G4: Structured Outputs & Artifacts
- **Gap:** Outputs are raw `tool_output` JSON in step cards
- **Current:** StepCard shows `tool_output` as a pre-formatted JSON block
- **Needed:** Semantic output renderers (tables, summaries, artifact cards, file downloads)

#### G5: Artifact Registry
- **Gap:** No artifact/file delivery mechanism
- **Current:** Tool outputs are in-memory JSON, no file persistence
- **Needed:** Artifact storage + download links in results panel

#### G6: Scheduling & Trigger
- **Gap:** No scheduling or delayed trigger support
- **Current:** Plan runs immediately after approval
- **Needed:** "Schedule for later" or "Save as template" or "Trigger on event"

#### G7: Mid-Execution Modification
- **Gap:** Cannot edit plan while running
- **Current:** Edit is only available for non-running plans
- **Needed:** Support for mid-execution step skips, parameter changes, or phase reordering

#### G8: Results Panel
- **Gap:** No dedicated Results view
- **Current:** Audit ledger after completion, but no structured results panel
- **Needed:** Results tab showing artifacts, summaries, and deliverables

#### G9: Monitoring Dashboard
- **Gap:** No live metrics dashboard
- **Current:** Metrics are in audit ledger after completion
- **Needed:** Real-time monitoring panel with charts, health, and resource usage

#### G10: Discovery & Reasoning Mode
- **Gap:** No explicit "discovery mode" or "reasoning conversation" before planning
- **Current:** Pulse goes straight to decomposition
- **Needed:** Multi-turn conversation phase before plan generation

---

## Findings & Recommendations

### Finding F-23: No Discovery Conversation Phase
**Severity:** P1 (user experience gap)  
**Evidence:** Current `createPlan` API immediately calls `SkillAwarePlanner.decompose` with the brief. There is no multi-turn discovery or requirement-gathering phase.  
**Impact:** Complex tasks get inadequate plans because Pulse doesn't gather enough context before planning.  
**Recommendation:** Add a `discovery` conversation type that collects requirements before plan creation. Plans should be generated only after the user confirms "the brief is complete, now create the plan."

### Finding F-24: Outputs are JSON Dumps, Not Artifacts
**Severity:** P1 (user experience gap)  
**Evidence:** `StepCard` in `AITaskPanel.jsx` lines 108-137 renders `tool_output` as a raw JSON pre block. No semantic rendering.  
**Impact:** Users see developer data, not business results.  
**Recommendation:** Build output type renderers: tables for tabular data, summaries for text, artifact cards for files, charts for metrics. Hide JSON behind "View raw output" accordion.

### Finding F-25: No Artifact Persistence or Download
**Severity:** P1 (functional gap)  
**Evidence:** Tool outputs are JSON stored in `RunStep.tool_output_json`. No file storage or download mechanism.  
**Impact:** Cannot deliver Word/Excel files or any binary artifacts.  
**Recommendation:** Add artifact storage (S3 or local mediafiles), artifact registry in `Run` model, download API endpoint, and artifact cards in results panel.

### Finding F-26: No Multi-Agent Coordination Semantics
**Severity:** P2 (feature gap)  
**Evidence:** Engine has one orchestrator role. `agent_role` exists in step metadata but no parallel execution or handoff logic.  
**Impact:** Cannot model true multi-agent workflows where agents collaborate or run in parallel.  
**Recommendation:** Extend planner to generate parallel phase strategies, update executor to support agent pools, and surface agent assignments prominently in UI.

### Finding F-27: No Monitoring Dashboard
**Severity:** P2 (observability gap)  
**Evidence:** Metrics are only visible in audit ledger after completion. No live dashboard.  
**Impact:** Admins cannot monitor long-running workflows in real-time.  
**Recommendation:** Build a monitoring panel in AI admin console with live metrics: active runs, step health, resource usage, error rate, cost burn.

### Finding F-28: No Mid-Execution Edit
**Severity:** P3 (flexibility gap)  
**Evidence:** `editPlan` and `editPlanStep` are only allowed for non-running plans (plans_service enforces this).  
**Impact:** Cannot adapt a running plan if requirements change mid-execution.  
**Recommendation:** Allow step parameter updates during pause, or support "insert step" / "skip step" operations on paused plans.

### Finding F-29: No Scheduling or Delayed Trigger
**Severity:** P3 (feature gap)  
**Evidence:** `runPlan` starts execution immediately. No scheduling or template workflow support.  
**Impact:** Cannot save a plan for later execution or create reusable workflow templates.  
**Recommendation:** Add `scheduled_at` field to Run model, cron-style scheduler, and "Save as template" in UI.

---

## Test Result Summary

**Status:** NOT EXECUTED (implementation gaps block full scenario)  

**Blockers:**
- G1: No discovery conversation (F-23)
- G4: No artifact delivery (F-25)
- G5: No artifact registry (F-25)
- G8: No results panel (F-24)

**Partial Support:**
- Plan creation, approval, execution, pause/resume, stop: ✅ EXISTS
- Step-level consent: ✅ EXISTS
- Live streaming: ✅ EXISTS
- Audit ledger: ✅ EXISTS

**Recommended Next Steps:**
1. Fix F-23: Add discovery conversation phase before plan generation
2. Fix F-25: Build artifact storage and delivery mechanism
3. Fix F-24: Build semantic output renderers for common types
4. Fix F-26: Enhance multi-agent coordination semantics
5. Re-run this scenario after fixes

---

## Conclusion

This test scenario validates that while Pulse has a solid foundation for agentic task orchestration (plan creation, approval, execution, audit), it lacks the enterprise-grade features needed for sophisticated multi-agent workflows:

- No discovery conversation
- No artifact delivery
- No structured result surfaces
- No live monitoring dashboard
- No multi-agent coordination semantics

To pass this scenario, Pulse needs to evolve from "single-agent step executor" to "multi-agent workflow orchestrator with discovery, execution, and delivery."
