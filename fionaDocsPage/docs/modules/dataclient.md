# DataClient

DataClient is Fiona's standalone research and data collection app. It is not part of the shared `fiona edit` GUI.

## Open The App

```bash
python3 -m fiona.cli dataclient
```

If Fiona is installed into the active environment:

```bash
fiona dataclient
```

## GUI Areas

The GUI has two main tabs:

- `Research`: quick topic mining and bounded deep research.
- `MiniExcel`: lightweight CSV/JSON/SQLite viewer and editor.

The app menu includes a `Miner` menu for starting quick mining, starting deep research, and clearing the miner log without switching tabs.

## Research Mode

Quick mode:

- searches DuckDuckGo HTML results
- scrapes the selected number of pages
- summarizes page text
- saves the results as CSV

Deep mode:

- starts from search result seed pages
- follows same-domain links by default
- obeys depth and page-limit controls
- records page depth and parent URL

CLI quick mining:

```bash
python3 -m fiona.cli dataclient mine "local desktop automation" --out ./research.csv --max-links 30
```

CLI deep research:

```bash
python3 -m fiona.cli dataclient deep "local desktop automation" --out ./deep-research.csv --seed-links 10 --depth 1 --page-limit 50
```

Deep mode is intentionally bounded. Use `--cross-domain` only when broader crawling is intentional.

## Output Columns

DataClient research exports use these columns:

- `topic`
- `url`
- `title`
- `summary`
- `depth`
- `parent_url`

## MiniExcel

MiniExcel can:

- open CSV, JSON, and SQLite tables
- display data in rows and columns
- edit the selected cell
- add rows
- add columns
- delete rows
- save or export the table
- use a formula bar for selected cells

Formula bar examples:

```text
=A1
=B1:B5
=SUM(B1:B5)
=AVG(C1:C10)
=LOWER(A1)
```

Supported safe functions include `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`, `LEN`, `LOWER`, and `UPPER`.

## Convert And Preview

Convert between table formats:

```bash
python3 -m fiona.cli dataclient convert ./research.csv --out ./research.json
python3 -m fiona.cli dataclient convert ./research.json --out ./research.db --table research
```

Preview a table from the terminal:

```bash
python3 -m fiona.cli dataclient view ./research.csv --limit 5
```
