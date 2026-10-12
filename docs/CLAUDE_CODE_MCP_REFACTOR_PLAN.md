# TradingAgents → Claude Code MCP/Skill Refactor

## Status

- Overall: **In progress**
- Current slice: **Claude Code plugin and MCP foundation**
- Last reviewed: 2026-09-20

## Confirmed intent

Turn TradingAgents from a standalone LLM-calling application into a local MCP
server plus Claude Code skill. Claude Code remains the model/provider client;
the Python process must not require an Anthropic/OpenAI LLM API key. Existing
data-provider keys (for example FRED or Alpha Vantage) remain supported.

The user should be able to invoke a workflow such as `/trading:analyze NVDA`
inside the Claude Code VS Code extension. Claude Code performs the reasoning;
TradingAgents provides market data, technical/fundamental/news context,
portfolio validation, memory, report persistence, and deterministic scoring.

## Architecture decisions

1. **One-way model boundary.** MCP is called by Claude Code. Python does not
   attempt to reuse the extension's private auth/session or call the model
   through an undocumented reverse channel.
2. **MCP-first, skill-driven orchestration.** The current analyst, research,
   trader, risk, portfolio, and reflection roles become a Claude Code workflow
   expressed in a skill/command. The Python MCP layer stays deterministic.
3. **Stable structured contracts.** MCP inputs and outputs use Pydantic models;
   decision payloads are validated before they are recorded.
4. **Compatibility before cutover.** Existing provider-backed graph/CLI code is
   retained as a legacy path until the MCP smoke tests and report compatibility
   checks pass. It is not used by MCP mode.
5. **Safety by default.** The system produces analysis and recommendations only;
   it does not place broker orders. Large backtests require explicit bounded
   inputs because each cell may require Claude reasoning.

## Dependency graph

```text
Claude Code command/skill
        ↓ tool calls
Local TradingAgents MCP server
        ↓
Deterministic briefing + validation + memory/report services
        ↓
Existing dataflows and report/memory formats
```

## Task list

### Phase 1 — Foundation

#### Task 1: Add deterministic MCP contracts and services

**Description:** Add a small core layer that can build structured analysis
briefings without constructing an LLM client. Reuse existing dataflows and
configuration; do not rewrite vendor adapters.

**Acceptance criteria:**

- [x] Health/config inspection reports data-vendor readiness without checking
      for LLM credentials.
- [x] A market briefing can resolve an instrument and return as-of metadata,
      data, source, and warnings in JSON-serializable form.
- [x] A portfolio payload can be validated/rendered using the existing models.

**Verification:** Unit tests with mocked vendor boundaries; import the new core
without importing `tradingagents.llm_clients`.

**Dependencies:** None

**Files likely touched:**

- `tradingagents/mcp/contracts.py`
- `tradingagents/mcp/services.py`
- `tests/test_mcp_services.py`

**Estimated scope:** Medium

#### Task 2: Expose a local stdio MCP server

**Description:** Register the deterministic services as MCP tools and provide a
stable `python -m tradingagents.mcp` entrypoint. Keep tool responses bounded and
machine-readable.

**Acceptance criteria:**

- [x] The server has a stdio entrypoint and advertises named tools when the MCP
      SDK is installed.
- [x] Invalid arguments return structured validation errors from the service
      boundary.
- [x] MCP startup code does not require an LLM provider/model/API key.

**Verification:** MCP client/transport smoke test plus direct module startup.

**Dependencies:** Task 1

**Files likely touched:**

- `tradingagents/mcp/server.py`
- `tradingagents/mcp/__main__.py`
- `pyproject.toml`
- `tests/test_mcp_server.py`

**Estimated scope:** Medium

### Checkpoint: MCP foundation

- [ ] New MCP unit/integration tests pass (pytest is unavailable in the current
      shell; syntax and direct contract smoke checks pass).
- [x] Direct contract/briefing fixture smoke checks pass.
- [x] Decision → report → memory → outcome round-trip smoke check passes.
- [ ] Existing test suite remains green.
- [ ] A clean environment can start the server without LLM keys.

### Phase 2 — Claude Code integration

#### Task 3: Add report, memory, decision-validation, and outcome tools

**Description:** Extract the persistence boundary currently embedded in the
graph so Claude Code can save a decision, write the existing report tree, read
prior lessons, and score settled outcomes.

**Acceptance criteria:**

- [x] `validate_and_record_decision` rejects invalid rating/schema payloads.
- [x] Successful records remain readable by existing memory/report utilities.
- [x] Outcome/alpha data is deterministic; reflection prose is supplied by the
      Claude Code workflow rather than generated inside MCP.
- [x] Settled decision logs can be aggregated without a model call.

**Verification:** Round-trip tests for decision → memory → report and pending →
settled outcome.

**Dependencies:** Task 1, Task 2

**Files likely touched:**

- `tradingagents/mcp/services.py`
- `tradingagents/mcp/contracts.py`
- `tradingagents/reporting.py`
- `tests/test_mcp_decision_lifecycle.py`

**Estimated scope:** Large

#### Task 4: Package the Claude Code skill and command

**Description:** Add the Claude Code project integration. The command accepts
ticker/date/asset type/analysts/portfolio and instructs Claude Code to execute
the analyst → bull/bear → research → trader → risk → portfolio workflow using
the MCP tools.

**Acceptance criteria:**

- [x] Plugin `.mcp.json` starts the local server on Windows and POSIX
      environments after package installation.
- [x] `/tradingagents:analyze` has explicit tool-use order, missing-data handling,
      output sections, and financial-safety language.
- [x] Skill output preserves the existing report sections and five-tier rating.

**Verification:** Static plugin/config validation and a manual Claude Code
discovery check via `/mcp` and the command palette.

**Dependencies:** Task 2, Task 3

**Files likely touched:**

- `.mcp.json`
- `commands/trading-analyze.md`
- `skills/trading-analysis/SKILL.md`
- `README.md`

**Estimated scope:** Medium

#### Task 4a: Keep legacy agent imports lazy

**Description:** Preserve the public `tradingagents.agents` factory API while
preventing MCP memory/report imports from eagerly loading LangChain agent
modules.

**Acceptance criteria:**

- [x] Importing MCP services and memory does not import an analyst module.
- [x] Existing factory imports remain available through lazy module exports.

**Verification:** `tests/test_mcp_no_llm_dependency.py` plus direct MCP
decision round-trip smoke test.

**Dependencies:** Task 1, Task 3

**Files touched:**

- `tradingagents/agents/__init__.py`
- `tests/test_mcp_no_llm_dependency.py`

**Estimated scope:** Small

### Checkpoint: End-to-end analysis

- [ ] Claude Code discovers the MCP server and command.
- [ ] A mocked NVDA analysis completes without an LLM API key in Python.
- [ ] `complete_report.md` and memory entries are created.

### Phase 3 — Compatibility and cutover

#### Task 5: Add bounded backtest/scoring workflow

**Description:** Expose deterministic score aggregation and a skill workflow
that asks Claude Code to process a bounded grid of cells. Preserve existing
settlement semantics and prevent accidental unbounded model usage.

**Acceptance criteria:**

- [ ] Backtest inputs require valid dates, tickers, and a maximum cell count.
- [ ] Scoring matches the existing `BacktestSummary` behavior for fixtures.
- [ ] Pending/unsettled cells are reported explicitly.

**Verification:** Fixture-based scoring and one bounded end-to-end grid.

**Dependencies:** Task 3, Task 4

**Files likely touched:**

- `tradingagents/mcp/services.py`
- `tradingagents/backtest.py`
- `skills/trading-analysis/SKILL.md`
- `tests/test_mcp_backtest.py`

**Estimated scope:** Medium

#### Task 6: Legacy isolation and documentation cutover

**Description:** Make MCP mode the documented default while preserving the
provider-backed standalone graph as an explicit legacy/optional path until the
compatibility suite is complete.

**Acceptance criteria:**

- [ ] README quickstart uses Claude Code + MCP and clearly separates data keys
      from LLM keys.
- [ ] Legacy CLI behavior is either explicitly labeled or guarded from being
      selected accidentally by MCP users.
- [ ] No MCP path imports or instantiates `create_llm_client`.

**Verification:** Full pytest suite, package build, install smoke test, and
manual Claude Code invocation.

**Dependencies:** Task 4, Task 5

**Files likely touched:**

- `README.md`
- `pyproject.toml`
- `cli/main.py`
- `tests/test_mcp_no_llm_dependency.py`

**Estimated scope:** Medium

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| MCP tool output overwhelms Claude context | High | Role-specific briefings, bounded article counts, provenance and warnings |
| Claude workflow drifts from old graph behavior | High | Preserve schemas/sections and add fixture-based rubric checks |
| Data-provider failures look like model conclusions | High | Structured warnings and explicit unavailable markers |
| Backtest causes unexpected usage/cost | Medium | Require max cells and make batch execution explicit |
| Windows stdio/Python path issues | Medium | Test `cmd /c`/native Python launch and document both paths |
| User mistakes data keys for LLM keys | Medium | Separate config validation and README setup examples |

## Current implementation notes

- The first implementation slice intentionally leaves the existing LLM graph
  untouched; it adds a new, opt-in MCP path beside it.
- The untracked `test_agentrouter.py` was present before this work and is left
  untouched.
- Completion means the MCP path is usable from Claude Code; deleting all legacy
  LLM provider code is a later cleanup only after the compatibility checkpoint.
