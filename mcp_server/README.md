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

## Connect to the remote demo

The hosted demo endpoint is:

`https://sellable-mcp.onrender.com/mcp`

**Availability note:** this endpoint returned `This service has been suspended.` during client testing on 2026-11-12. The configurations below show the intended remote setup, but remote connectivity is currently unverified. Use the local STDIO setup below to run the server.

The public demo is designed to provide an isolated store and a signed ₹2,000 mission for books and stationery, with electronics forbidden. Payments are simulated.

### Cline — remote

Open Cline → MCP Servers → Configure MCP Servers and add this entry to `mcpServers`:

```json
{
  "mcpServers": {
    "sellable": {
      "type": "streamableHttp",
      "url": "https://sellable-mcp.onrender.com/mcp"
    }
  }
}
```

### Zed — remote

Open Settings → AI → MCP Servers → Add Server → Add Remote Server, or add this to your Zed settings:

> Zed may initiate an OAuth flow when a remote server has no Authorization header. The
> SELLABLE demo does not document OAuth support, so this configuration is an example only
> and is not verified. Prefer the local STDIO configuration below.

```json
{
  "context_servers": {
    "sellable": {
      "url": "https://sellable-mcp.onrender.com/mcp"
    }
  }
}
```

### Continue — remote

Create a YAML file in `.continue/mcpServers/`, for example `sellable-remote.yaml`:

```yaml
name: SELLABLE MCP Remote
version: 1.0.0
schema: v1

mcpServers:
  - name: sellable
    type: streamable-http
    url: https://sellable-mcp.onrender.com/mcp
```

Continue MCP servers are available in Agent mode.

## Run locally (STDIO)

Local mode runs the server process on your machine and does not depend on the hosted demo.

### Prerequisites

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) for the one-line installation, or a local SELLABLE checkout

### Option A: install from PyPI

Add this configuration to the relevant MCP client. The server communicates over standard input/output (STDIO).

```json
{
  "command": "uvx",
  "args": ["sellable-mcp"]
}
```

For Cline, place it under the `mcpServers` key:

```json
{
  "mcpServers": {
    "sellable": {
      "command": "uvx",
      "args": ["sellable-mcp"]
    }
  }
}
```

### Option B: run from a local checkout

Clone the repository, create its virtual environment, and install the project:

```bash
git clone https://github.com/HarshDubey23/SELLABLE.git
cd SELLABLE
uv sync
```

Use the absolute path to the environment's executable in your client configuration:

`/absolute/path/to/SELLABLE/.venv/bin/sellable-mcp`

Do not copy the example path literally. Replace it with the path on your machine.

### Cline — local

Open Cline → MCP Servers → Configure MCP Servers. Add:

```json
{
  "mcpServers": {
    "sellable": {
      "command": "/absolute/path/to/SELLABLE/.venv/bin/sellable-mcp"
    }
  }
}
```

### Zed — local

Open Settings → AI → MCP Servers → Add Server → Add Local Server, or add this to your Zed settings:

```json
{
  "context_servers": {
    "sellable": {
      "command": "/absolute/path/to/SELLABLE/.venv/bin/sellable-mcp",
      "args": []
    }
  }
}
```

### Continue — local

Create `.continue/mcpServers/sellable.yaml` in your workspace:

```yaml
name: SELLABLE MCP
version: 1.0.0
schema: v1

mcpServers:
  - name: sellable
    type: stdio
    command: /absolute/path/to/SELLABLE/.venv/bin/sellable-mcp
    args: []
```

Replace the command path with your local absolute path. Switch Continue to Agent mode to use MCP tools.

## Client verification

The following local configurations were checked on macOS. Tool discovery and server connection are reported separately; a green connection indicator alone does not prove that tools were discovered or invoked.

| Client | Version | Local verification |
|---|---:|---|
| Cline | 4.0.12 | 10 SELLABLE tools discovered |
| Zed | 1.28.1 | Server showed active; tool discovery and invocation not verified |
| Continue | 2.0.0 | 10 SELLABLE tools discovered |

Screenshots captured during local setup:

- `screenshots/cline-local-mcp.png`
- `screenshots/continue-local-mcp.png`

Tool discovery was verified in Cline and Continue. An actual tool invocation was not part of this verification.

### Official client documentation

- [Cline MCP documentation](https://docs.cline.bot/mcp/mcp-overview)
- [Zed MCP documentation](https://zed.dev/docs/ai/mcp)
- [Continue MCP documentation](https://docs.continue.dev/customize/deep-dives/mcp)

### Host your own remote server

```bash
# Public demo
sellable-mcp serve --http --sandbox --host 0.0.0.0 --port 8765

# Private: requests require the token
SELLABLE_MCP_TOKEN=$(openssl rand -hex 24) sellable-mcp serve --http --host 0.0.0.0 --port 8765
```

The HTTP server uses Streamable HTTP, JSON responses, one `Mcp-Session-Id` per client, and a rate limit of 90 requests per minute per IP. Use `SELLABLE_ALLOWED_ORIGINS` to restrict browser origins.

## Give the agent a mission (you, not the agent)

Missions are signed with a key that lives in `~/.sellable/key` and is never exposed as a tool:

```bash
uvx sellable-mcp mission new \
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
