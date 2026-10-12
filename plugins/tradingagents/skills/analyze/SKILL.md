---
name: analyze
description: Run a TradingAgents-style stock or crypto analysis using the local TradingAgents MCP server and the current Claude Code provider. Use when the user asks for market analysis, a trade thesis, a portfolio rating, a backtest cell, or a TradingAgents report.
argument-hint: <TICKER> [YYYY-MM-DD] [stock|crypto]
---

# TradingAgents analysis

Use the local `tradingagents` MCP server for data and persistence. Claude Code
is the only reasoning/model client in this workflow. Never ask the Python
server to create an Anthropic/OpenAI client, and never ask the user for an LLM
API key for this skill.

## Inputs

Parse `$ARGUMENTS` as:

1. `ticker` (required)
2. `trade_date` (optional; use today's date if omitted)
3. `asset_type` (optional; `stock` by default, or `crypto`)

If the user supplies a portfolio JSON object, pass it to
`mcp__tradingagents__validate_portfolio` before making a sizing recommendation. Do
not pass a filesystem path as a portfolio object; read the file in Claude Code
and pass its parsed JSON.

## Required workflow

1. Call `mcp__tradingagents__health`. Explain any data-vendor warning before drawing
   a conclusion. A degraded data vendor is not evidence for Buy, Hold, or Sell.
2. Call `mcp__tradingagents__get_analysis_briefing` for `market`, `fundamentals`,
   `news`, and `social` (or only the user-selected analyst set). Use the same
   ticker, date, asset type, and lookback for every call. These calls may run in
   parallel.
3. Write four clearly labelled analyst reports. Every claim about price,
   indicators, fundamentals, or news must point to a returned source. Treat
   `DATA_UNAVAILABLE` and `NO_DATA_AVAILABLE` as unavailable; never fill the
   gap from memory.
4. Run the debate in this order:

   - Bull researcher: strongest evidence for upside.
   - Bear researcher: strongest evidence for downside and what invalidates the
     bull case.
   - Research manager: choose exactly one of Buy, Overweight, Hold, Underweight,
     Sell and give strategic actions.
   - Trader: choose Buy, Hold, or Sell with entry/stop/sizing guidance when the
     data supports it.
   - Aggressive, conservative, and neutral risk reviewers: identify sizing and
     downside constraints.
   - Portfolio manager: produce the final five-tier rating and investment thesis.

5. Call `mcp__tradingagents__get_prior_lessons` before the final portfolio decision.
   Only use lessons returned for the requested point-in-time date.
6. Produce the final decision payload with exactly this shape:

```json
{
  "rating": "Buy | Overweight | Hold | Underweight | Sell",
  "executive_summary": "...",
  "investment_thesis": "...",
  "price_target": 0,
  "time_horizon": "..."
}
```

Use `null` when a price target or time horizon is not supported by the data.
7. Call `mcp__tradingagents__validate_and_record_decision` only after the final
   decision and reports are complete. Pass the reports as a JSON object using
   these keys when available: `market_report`, `sentiment_report`,
   `news_report`, `fundamentals_report`. The tool validates the decision,
   records memory, and writes the compatible markdown report tree.
8. Present the rating, thesis, warnings, and the returned report path. State
   that this is research and not an order or personalized financial advice.

For a later evaluation request, use `mcp__tradingagents__score_decision_log`
after outcomes have settled. It is deterministic and does not spend another
model call.

## Guardrails

- Never place or simulate a broker order.
- Never claim that a missing vendor response is bearish or bullish.
- Preserve exchange suffixes and exact asset identity.
- Do not use future dates.
- Do not run an unbounded backtest from a broad prompt. Ask for a bounded
  ticker/date grid and a maximum number of cells first.
- Do not reveal environment variable values or credentials in the report.
