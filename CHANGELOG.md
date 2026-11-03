# Changelog

All notable changes to SELLABLE are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). The version number is the one the
MCP server reports to clients (`mcp_server/server.py`) and the one published
on PyPI as `sellable-mcp`.

## [Unreleased]

## [2.0.0] - 2026-11-03

First release published to PyPI. The code is the MCP server line that the
`v1.0.0` GitHub release (2026-10-26) shipped from source; this release adds
packaging and maintenance tooling around it.

### Added
- `pip install sellable-mcp` / `uvx sellable-mcp`: published package with
  project metadata, classifiers and links.
- Release workflow: a version tag builds the package, checks that the tag,
  `pyproject.toml`, the server and this changelog agree, installs the wheel in
  a clean environment, publishes through PyPI Trusted Publishing and creates
  the GitHub release from this file.
- Contributor documentation: `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, issue and pull request templates, and `AGENTS.md`
  for coding agents.
- Automated pull request review that reads `AGENTS.md` and focuses on the
  money path.
- Evidence workflow: push a `truth/*` branch to regenerate
  `docs/generated/truth.json` on a clean runner. README numbers refreshed
  from it (618 tests passing).
- `examples/openai_tools_agent.py`: SELLABLE's MCP tools exposed as
  OpenAI-style function tools for any chat-completions agent loop.

### Already in the server (shipped with v1.0.0)
- Remote MCP over Streamable HTTP with a public sandbox; local stdio server.
- Proposals limited to `{sku, qty}`; prices and payee come from the
  server-side catalog.
- Deterministic gateway, rules R1-R12, with single-use approvals bound to the
  proposal hash and a hash-chained audit log.
- Live-LLM prompt-injection benchmark (`eval/llm_injection/`): 864 episodes,
  three models, results reproducible from the committed episodes.

[Unreleased]: https://github.com/HarshDubey23/SELLABLE/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/HarshDubey23/SELLABLE/compare/v1.0.0...v2.0.0
