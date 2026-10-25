# ZizAI Agent Router

- Rules updated: 2026-10-24

- Start with [docs/README.md](docs/README.md), then open the assigned GitHub Issue from [the task index](docs/tasks/README.md). Read its parent Issue and required references. Task/Subtask scope, state, decisions, and results are maintained in Issues; existing Task Markdown is an immutable migration record.
- Before creating or splitting a Task, read [Task/Subtask authoring rules](docs/tasks/task-rules.md) and use the linked templates.
- When creating, updating, or assessing a Task/Subtask, classify dependencies as mandatory prerequisites, mutual coordination, or unresolved under [dependency rules](docs/tasks/task-rules.md#dependency-classification). Record required deliverables, affected stages, and fulfillment evidence in the assigned Issue; apply conditions to the relevant scope without changing existing authority or constraints.
- Read the Task's `References` before opening unrelated documentation. Load only the sections needed for the current decision.
- Current Specifications are under `docs/features/`; repository architecture is defined in `docs/features/architecture.md`.
- Implementation and verification rules are defined in `docs/features/coding-rules.md`; cleanup and responsibility changes use `docs/features/refactor-policy.md`.
- Before creating a Task, planning implementation, or fixing an Edit Scope, identify the responsibility area and follow [canonical-source preflight](docs/features/coding-rules.md#canonical-source-and-synchronized-copies). Do not infer ownership or editability from names or paths; leave unresolved ownership explicit.
- Document roles, Task/Subtask structure, and writing conventions follow [docs/README.md](docs/README.md#document-responsibilities).
- Task authority is limited to its explicit Goal, Scope, Constraints, and Acceptance Criteria. General directions such as "continue" or "implement" do not authorize changes to Current Specifications or existing constraints.
- Project work must be understandable and verifiable from tracked Project assets. Local-only `.agents/` and `.codex/` resources may assist execution but are never required Project references.

## Decision ownership (working guideline)

- Follow [approval boundaries and owner evaluation levels](docs/README.md#approval-boundaries). Present related design choices together and continue ordinary work already authorized without repeating approval requests.
- Codex defines and verifies [security quality targets](docs/features/coding-rules.md#security-quality-target). Task constraints, Current Specifications, and required approvals remain authoritative.
