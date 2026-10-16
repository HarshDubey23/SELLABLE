# SELLABLE MCP server

**Give any AI agent a shopping tool that structurally cannot spend your money.**

Most "agent buys things" setups hand the model a payment tool with an `amount` and a `payee`.
A single line of injected text on a product page can then become a payment instruction.
This server gives the agent no such words:

| The agent can | The agent cannot |
|---|---|
| search the catalog, read products | state a price or an amount |
| see the missions you signed | choose who gets paid |
| propose `{sku, qty}` baskets | create a mission or raise a budget |
| place an order the gateway approved, once | reuse an approval, read the signing key |

Every proposal goes through SELLABLE's deterministic gateway (rules R1–R12: budget, forbidden
and allowed categories, price integrity, mission signature, expiry, revocation, rate limit),
then through a cumulative-spend and stock check. On APPROVE the agent gets a single-use approval
valid for 10 minutes, bound to the proposal hash. Every proposal, verdict and order is written to
a hash-chained audit log.

No dependencies beyond the Python standard library. Payments use a **simulated provider**:
orders are recorded locally and nothing is charged.

## Install (no clone)

This is a **local STDIO server**: your MCP client starts it on your computer and everything,
including the signing key, stays in `~/.sellable` (Windows: `%USERPROFILE%\.sellable`; override
with `SELLABLE_HOME`). It is not a hosted service.

**1. Install [uv](https://docs.astral.sh/uv/).**

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal afterwards so `uvx` is on your PATH.

**2. Add it to your client.** Each client has its own file and format.

<details open><summary><b>Claude Code</b></summary>

```bash
claude mcp add sellable -- uvx --from git+https://github.com/HarshDubey23/SELLABLE sellable-mcp
```

`claude mcp list` should show `sellable … ✓ Connected`.
</details>

<details><summary><b>Claude Desktop</b>, <b>Cursor</b> and <b>Windsurf</b></summary>

| Client | Config file |
|---|---|
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` (Windows), `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |
| Cursor | `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project) |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |

```json
{
  "mcpServers": {
    "sellable": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/HarshDubey23/SELLABLE", "sellable-mcp"]
    }
  }
}
```

Restart the client after saving. If a GUI client can't find `uvx`, replace `"uvx"` with the
full path from `where uvx` (Windows) or `which uvx`.
</details>

<details><summary><b>VS Code</b></summary>

VS Code uses a different shape: the top-level key is `servers`, not `mcpServers`. Save as
`.vscode/mcp.json` and use the tools from Copilot Chat in agent mode.

```json
{
  "servers": {
    "sellable": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/HarshDubey23/SELLABLE", "sellable-mcp"]
    }
  }
}
```
</details>

**n8n is not supported.** n8n's MCP Client Tool node connects to remote HTTP servers, and this
server is STDIO only.

Prefer pip? Run `pip install git+https://github.com/HarshDubey23/SELLABLE`, then use
`"command": "sellable-mcp"` with no args.

## Give the agent a mission (you, not the agent)

Missions are signed with a key that lives in `~/.sellable/key` and is never exposed as a tool:

```bash
uvx --from git+https://github.com/HarshDubey23/SELLABLE sellable-mcp mission new --budget 2000 --category books --category stationery --forbid electronics --hours 24
```

(One line, so it pastes into PowerShell, Command Prompt and bash alike.)

Then ask your agent something like *"buy me two novels for my nephew"*. It will call
`list_missions` → `search_catalog` → `propose_purchase` → `place_order`.

Other commands: `mission list`, `mission revoke <id>`, `orders`, `audit verify`, `config`.

## Stop, revoke, remove

1. Revoke any open mission: `sellable-mcp mission revoke <id>`. Already-approved orders on a
   revoked mission are refused too.
2. Remove the `sellable` entry from your client config (Claude Code: `claude mcp remove sellable`)
   and restart the client.
3. To erase everything, delete `~/.sellable` (the signing key, missions, orders and audit log).

## Tools

| Tool | What it does |
|---|---|
| `search_catalog` | text search with category and max-price filters (361 products, 9 categories) |
| `get_product` | full record: price, attributes, compatibility, return policy, stock left |
| `list_categories` | categories with counts |
| `list_missions` | your signed missions with budget, spent, remaining, scope, expiry |
| `propose_purchase` | `{mission_id, items:[{sku, qty}]}` → APPROVE with `approval_id`, or REJECT with rule and hint |
| `place_order` | `{approval_id}` → executes that basket once, at catalog prices |
| `get_order`, `list_orders` | order lookup |
| `get_policy` | the rules, in plain words |
| `verify_audit_log` | recompute the hash chain |

## What is tested

`tests/mcp/test_mcp_server.py` drives the server over real stdio JSON-RPC:

- the happy path, plus single-use approvals (a replayed approval is refused);
- out-of-scope, over-budget, unknown mission and unknown SKU proposals are rejected;
- cumulative spend: a second basket that would exceed the budget is rejected;
- **editing the budget in `missions.json` on disk fails the signature check (R9)**;
- a revoked mission refuses both new proposals and already-approved orders;
- editing one audit entry is detected at exactly that entry;
- no tool's input schema contains a price, amount or payee field.

## Limits, stated plainly

- The catalog is bundled demo data, and payments are simulated. Hooking a real provider means
  replacing `place_order`'s execution step. The gateway doesn't change.
- Custody is local: anything else on your machine that can read `~/.sellable/key` (for example
  another MCP server with filesystem access) could sign missions. Keep that directory private.
- The gateway stops the agent from spending outside your mission. It doesn't stop the agent from
  making a poor choice *inside* it.
