# diagram-gen

Scans `mintdocs/` for mermaid code blocks, extracts them to `sources/`, and
renders each to a PNG in `mintdocs/images/diagrams/`.

## Prerequisites

Node.js must be installed. Install the Mermaid CLI globally:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc --version
```

## Usage

Run from the repo root:

```bash
uv run python diagram-gen/generate.py
```

## Output

| Path | What it is |
|---|---|
| `diagram-gen/sources/*.mmd` | Extracted mermaid source files (committed) |
| `mintdocs/images/diagrams/*.png` | Rendered PNG images (committed) |

## Naming convention

`{mdx-stem}--diagram-{n}.mmd` / `.png`

For example, the second diagram in `architecture-overview.mdx` produces:
- `sources/architecture-overview--diagram-2.mmd`
- `mintdocs/images/diagrams/architecture-overview--diagram-2.png`

## Pre-commit hook

The `.pre-commit-config.yaml` at the repo root runs `generate.py` automatically
before every commit that touches `.mdx` files. Install the hook once:

Run both from the repo root (`d:\projects\privatehomebox`):

```bash
uv tool install pre-commit
pre-commit install
```
