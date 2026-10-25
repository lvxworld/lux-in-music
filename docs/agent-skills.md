# Agent skills during development

Use this guide at task start and when an iteration moves between design,
implementation, diagnosis, review, and handoff. It is part of the
[shared harness](harness.md). [AGENTS.md](../AGENTS.md) remains the repository
contract; skills supply optional workflows within that contract.

## Suggest the next useful skill

1. Identify the current need using the table below. Recommend one skill, or two
   complementary skills, only when they would materially help the next step.
2. Check the current session's skill catalogue. Select Matt Pocock's plugin
   entry when another plugin exposes the same name, especially `code-review`.
   Read the selected `SKILL.md` before using it. An installed cache alone does
   not establish that a skill is available in this session.
3. Explain the recommendation in one sentence, in the user's language, tied to
   the actual task: "I suggest `prototype` to compare the stem-selection layouts
   before implementing one." Suggest again when the need changes, rather than
   repeating the suggestion on every turn.
4. Respect the skill's invocation policy. Propose user-invoked workflows and
   wait for the user to choose them; use implicitly invocable skills when they
   fit work already requested. Continue independent, authorized work while an
   optional suggestion is pending. For a small, clear change, proceed directly.

If a useful skill is unavailable, say so briefly and continue with the normal
harness workflow. Users can select an available skill in the interface or ask
"Use Matt Pocock's `<skill-name>` skill for this task."

## Choose by situation

| Situation | Skill | Lux In Music example |
| --- | --- | --- |
| An idea needs decisions | `grill-with-docs` | Define song continuation behavior, limits, and controls; record agreed terminology and decisions. |
| Agreed discussion needs a specification | `to-spec` | Capture export behavior, acceptance criteria, test boundaries, and scope. |
| A feature needs several deliverables | `to-tickets` | Split a feature into independently verifiable API/UI/test slices with dependencies. |
| One defined ticket is ready | `implement` | Implement job cancellation, test it, and review the result. |
| Behavior needs test-first development | `tdd` | Exercise queue or adapter behavior using fake transports and temporary files. |
| A whole spec has ready tickets | `implement-spec` | Coordinate independent tickets in separate worktrees and integrate their changes. |
| Something fails or becomes slow | `diagnosing-bugs` | Reproduce a stuck job or model-switch regression before changing code. |
| UI or state behavior is uncertain | `prototype` | Compare stem-selection layouts or explore queue transitions in a disposable prototype. |
| Upstream facts are missing | `research` | Verify audio.cpp continuation capabilities against official docs and source. |
| A module is difficult to change | `improve-codebase-architecture` | Survey provider/adapter friction and evaluate focused refactoring candidates. |
| Changes are ready for review | `code-review` | Review against both repository standards and the originating spec, with an explicit base ref. |
| A PR description is needed | `pr` | Present the change, before/after evidence, reversibility, and affected behavior. |
| A session exposed recurring mistakes | `retro` | Propose navigation improvements or deterministic checks that would have caught them. |
| The right workflow is unclear | `ask-matt` | Choose a skill or sequence for the current problem. |
| Work moves to another session | `handoff` | Preserve decisions, verified results, unresolved questions, and the next step. |
| An explanation did not land | `wait-what` | Explain the previous response again in simpler language. |

## Scale the workflow to the work

- **Small fix:** implement directly, or use `diagnosing-bugs` when the cause is
  unclear; verify at the changed boundary.
- **Normal feature:** `grill-with-docs` when decisions remain, then `to-spec`
  and `implement`; `implement` includes review. Use `pr` when preparing a PR.
- **Larger feature:** add `to-tickets`; choose `implement-spec` when dependencies
  are explicit and parallel work is useful. It includes final code review.
- **After a difficult session:** suggest `retro`. Present its recommendations
  before applying changes to the development environment.

Use `setup-matt-pocock-skills` when a chosen workflow needs issue-tracker or
domain-document configuration that is missing. Reuse this harness's existing
architecture, progress notes, and requirements rather than duplicating them.
Installing the plugin and configuring a repository are separate steps.

## Keep Lux verification authoritative

Use the commands and evidence requirements in [the harness](harness.md).
For generated-audio changes, include a real audio trial and listening check;
fake-provider tests establish application behavior, not musical quality.
Use synthetic lyrics and prompts in shared examples and evidence.
Record results and limitations in [progress notes](progress.md).

The plugin owns skill implementations and dependencies; this document owns
Lux-specific selection guidance. After plugin updates, verify changed skill
behavior against its current instructions. See
[Matt Pocock's skills](https://github.com/mattpocock/skills) and
[Codex skill documentation](https://learn.chatgpt.com/docs/build-skills).
