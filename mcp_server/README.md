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

## Install (one line, no clone)

You need [uv](https://docs.astral.sh/uv/). Claude Desktop (`claude_desktop_config.json`), Cursor
(`~/.cursor/mcp.json`) and Windsurf (`mcp_config.json`) take this `mcpServers` block:

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

**VS Code** reads `.vscode/mcp.json`, which uses a top-level `servers` key instead:

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

**Claude Code** adds it with one command:

```bash
claude mcp add --transport stdio sellable -- uvx --from git+https://github.com/HarshDubey23/SELLABLE sellable-mcp
```

**n8n** can't use it: n8n's MCP Client Tool connects to a remote (SSE) endpoint, and this server
runs locally over stdio.

Prefer pip? Run `pip install git+https://github.com/HarshDubey23/SELLABLE`, then use
`"command": "sellable-mcp"` with no args.

## Give the agent a mission (you, not the agent)

Missions are signed with a key that lives in `~/.sellable/key` and is never exposed as a tool:

```bash
uvx --from git+https://github.com/HarshDubey23/SELLABLE sellable-mcp mission new \
    --budget 2000 --category books --category stationery --forbid electronics --hours 24
```

Then ask your agent something like *"buy me two novels for my nephew"*. It will call
`list_missions` → `search_catalog` → `propose_purchase` → `place_order`.

Other commands: `mission list`, `mission revoke <id>`, `orders`, `audit verify`, `config`.

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
