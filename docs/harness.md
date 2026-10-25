# Shared contributor harness

The harness is a repository workflow: instructions, product contracts, executable
checks, and handoff notes. It works with a normal terminal or any coding CLI and
does not run an autonomous agent or depend on one agent vendor's SDK.

## Files and responsibilities

| File | Purpose |
| --- | --- |
| `AGENTS.md` | Canonical instructions and commands; short enough to load routinely |
| `CONTRIBUTING.md` | Human contributor workflow |
| `docs/architecture.md` | Product requirements, model boundaries, recorded design direction |
| `harness/requirements.json` | Acceptance scenarios, implementation status, issue links and test selectors |
| `docs/progress.md` | Verified state, open limitations, next steps |
| `docs/agent-skills.md` | Task-based skill suggestions, Lux examples, and optional development flows |
| `scripts/check.py` | Portable baseline and application verification entry point |
| `tests/` | Offline harness/application regression checks |
| `scripts/check_ui.py` | Isolated browser flow using fake providers/downloads |
| `.github/workflows/checks.yml` | Baseline and offline application gates on pushes and pull requests |

## CLI compatibility

AGENTS.md is an open instruction format supported by multiple agents. Automatic
discovery varies by tool and version. For a CLI that does not discover it, start
with: “Read AGENTS.md and the linked architecture before changing this repository.”
Anyone can run the same verification command without an AI tool.

`CLAUDE.md` imports `AGENTS.md`; `GEMINI.md` and
`.github/copilot-instructions.md` direct their readers to it. These small bridges
carry no separate product rules. Keep all actual instructions in AGENTS.md.
Aider can be configured to read AGENTS.md using its `read` setting; Gemini can
configure its context filename to AGENTS.md instead of using the bridge.

## Skills during iterations

At task start and phase changes, use [agent skill guidance](agent-skills.md)
to suggest a relevant Matt Pocock skill when it would help. It covers design,
diagnosis, implementation, review, and handoff, with examples for Lux In Music.
The discovery pointer also lives at the top of `docs/progress.md`, which
AGENTS.md already requires contributors to read when starting a task.
Skills are optional; contributors and CI can use the harness without the plugin.

## Commands and what they prove

```bash
python3 scripts/check.py
.venv/bin/python scripts/check.py --full
python3 scripts/check.py --require-complete
```

The baseline uses Python 3.11+, Node.js and Bash. It checks project-owned files
for retired branding, metadata/lock agreement, Python/JavaScript/shell syntax,
instruction bridges, and requirement-ledger structure. It also runs the harness's
own regression tests. It does not install dependencies or download weights.

`--full` adds offline application tests using installed Python dependencies:
bootstrap scripts with fake installers, empty-install API/library behavior,
license gates, precision manifests, download integrity/resume/cancellation,
profile persistence, runtime compatibility and provider-independent generation.
Runtime calls are faked. An unavailable dependency fails the check.
Available tests for planned work also run, without promoting its status.

The separate browser check needs Playwright and an installed Chrome:

```bash
uv run --no-project --with playwright python scripts/check_ui.py
```

It runs an isolated app with tiny fake files, never touches real Settings/model
data, and covers Settings-first navigation, licensing, independent BF16/F32
selection, activation, capability controls, generation, library and mobile
navigation. `LUX_TEST_BROWSER` can specify another installed Chrome executable.
Screenshots go to ignored `outputs/checks/ui/`, or a chosen `--artifacts` directory.
The browser check is separate from GPU/network-free CI; Playwright may need a
one-time dependency download, but the test never downloads a browser or model.

`--require-complete` is a product-readiness audit. It requires `--full` checks and
fails while any recorded requirement is planned. It is expected to fail during
the song-ending work. Normal CI can pass while that feature is still planned;
the output explicitly lists those features. Passing checks never claim that an
song-ending behavior or audio quality has been verified.

The baseline scans files tracked by Git plus new, nonignored files. A source
archive without Git falls back to the project tree, excluding generated data,
dependencies, and the vendored runtime. It checks filenames as well as contents.

## Deliver one requirement

Read its acceptance scenarios and related issue. Add the smallest useful tests at
the real boundary, implement the behavior, and run the relevant checks. Add an
automated `unittest` selector to its `tests` list when setting `status` to
`implemented`. The full harness runs the unique selectors shared by implemented requirements;
a missing, empty, or skipped test cannot establish completion.

Record results and limitations in `docs/progress.md`. UI requirements also need a
user-flow check; generated music needs a saved profile/seed, completion signals,
and a listening check. A mock cannot establish GPU support or musical quality.
Keep evidence for failed trials too. Amend an acceptance scenario only when the
product decision actually changes, recording the reason in the architecture.

## Basis and limits

This structure follows the [AGENTS.md open format](https://agents.md/),
[GitHub's repository instruction guidance](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions),
and [Claude's instruction/import documentation](https://code.claude.com/docs/en/memory).
[Anthropic's harness research](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
informs the focused requirement list, explicit verification, and session handoffs.
Research examples are design input, not a requirement to run multiple agents.

Instructions guide contributors; executable checks catch the specific regressions
they cover. Neither can prove every architectural or product rule automatically.
Broaden the tests when a concrete new behavior is implemented.
