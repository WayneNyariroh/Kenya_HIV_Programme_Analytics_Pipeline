#!/usr/bin/env python
"""Runs the Kenya health notebook from a terminal and prints cell progress
 and display outputs, and finally verifies the resulting DuckDB file.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def configure_terminal() -> None:
    """Avoid crashes when an older Windows terminal cannot encode a symbol."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def parse_args(project_dir: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute kenya_health_pipeline_v2.ipynb cell by cell, print its "
            "outputs, and report the generated DuckDB path."
        )
    )
    parser.add_argument(
        "--notebook",
        type=Path,
        default=project_dir / "kenya_health_pipeline_v2.ipynb",
        help="Notebook to run (default: kenya_health_pipeline_v2.ipynb beside this script).",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=project_dir / "database" / "kenya_health_data.duckdb",
        help="Database expected from the notebook (default: kenya_health_data.duckdb beside this script).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Maximum seconds allowed for one cell (default: 900).",
    )
    parser.add_argument(
        "--save-executed",
        nargs="?",
        const="kenya_health_pipeline_v2.executed.ipynb",
        metavar="PATH",
        help=(
            "Optionally save the newly executed notebook. If PATH is omitted, "
            "save kenya_health_pipeline_v2.executed.ipynb beside the script."
        ),
    )
    return parser.parse_args()


def require_notebook_dependencies() -> tuple[Any, Any, Any]:
    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import CellExecutionError
    except ModuleNotFoundError as exc:
        print("ERROR: The terminal runner needs Jupyter execution packages.")
        print("Install them with:")
        print(f'  "{sys.executable}" -m pip install nbformat nbclient ipykernel')
        print(f"Missing module: {exc.name}")
        raise SystemExit(2) from exc
    return nbformat, NotebookClient, CellExecutionError


def first_code_line(source: str) -> str:
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:100]
    return "code"


def markdown_heading(source: str) -> str | None:
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return None


def chart_description(spec: dict[str, Any]) -> str:
    title = spec.get("title")
    if isinstance(title, dict):
        title = title.get("text")
    if isinstance(title, list):
        title = " ".join(str(part) for part in title)
    mark = spec.get("mark", "chart")
    if isinstance(mark, dict):
        mark = mark.get("type", "chart")
    details = [str(mark)]
    if title:
        details.append(str(title))
    return " | ".join(details)


def print_rich_output(data: dict[str, Any]) -> None:
    vega_keys = [
        "application/vnd.vegalite.v5+json",
        "application/vnd.vegalite.v4+json",
        "application/vnd.vega.v5+json",
    ]
    for key in vega_keys:
        if key in data:
            print(f"[DISPLAY: Altair/Vega-Lite] {chart_description(data[key])}")
            return

    if "text/plain" in data:
        text = data["text/plain"]
        if isinstance(text, list):
            text = "".join(text)
        text = str(text)
        if text.startswith("alt."):
            print(f"[DISPLAY: Altair chart] {text}")
        else:
            print(text)
        return

    if "image/png" in data:
        encoded = data["image/png"]
        size = len(encoded) if hasattr(encoded, "__len__") else 0
        print(f"[DISPLAY: PNG image generated, encoded size {size:,} characters]")
        return

    if "image/jpeg" in data:
        print("[DISPLAY: JPEG image generated]")
        return

    if "text/html" in data:
        print("[DISPLAY: HTML output generated]")
        return

    mime_types = ", ".join(sorted(data)) or "unknown"
    print(f"[DISPLAY: rich output; MIME types: {mime_types}]")


def print_cell_outputs(cell: Any) -> None:
    outputs = cell.get("outputs", [])
    if not outputs:
        print("[no displayed output]")
        return

    for output in outputs:
        output_type = output.get("output_type")
        if output_type == "stream":
            text = output.get("text", "")
            if isinstance(text, list):
                text = "".join(text)
            print(str(text), end="" if str(text).endswith("\n") else "\n")
        elif output_type in {"display_data", "execute_result"}:
            print_rich_output(output.get("data", {}))
        elif output_type == "error":
            traceback = output.get("traceback", [])
            cleaned = "\n".join(ANSI_ESCAPE.sub("", line) for line in traceback)
            print(cleaned or f"{output.get('ename')}: {output.get('evalue')}")
        else:
            print(f"[OUTPUT: {output_type or 'unknown'}]")


def execute_notebook(notebook_path: Path, project_dir: Path, timeout: int,) -> tuple[Any, int]:
    nbformat, NotebookClient, CellExecutionError = require_notebook_dependencies()
    notebook = nbformat.read(notebook_path, as_version=4)
    code_total = sum(
        cell.cell_type == "code" and bool(cell.source.strip())
        for cell in notebook.cells
    )

    client = NotebookClient(
        notebook,
        timeout=timeout,
        startup_timeout=120,
        kernel_name="python3",
        allow_errors=False,
        resources={"metadata": {"path": str(project_dir)}},
        record_timing=True,
    )

    execution_count = 0
    started = time.perf_counter()
    print(f"Notebook: {notebook_path}")
    print(f"Working directory: {project_dir}")
    print(f"Started: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print(f"Code cells: {code_total}")
    print("=" * 78)

    try:
        with client.setup_kernel():
            for cell_index, cell in enumerate(notebook.cells):
                if cell.cell_type == "markdown":
                    heading = markdown_heading(cell.source)
                    if heading:
                        print(f"\n### {heading}")
                    continue
                if cell.cell_type != "code" or not cell.source.strip():
                    continue

                execution_count += 1
                description = first_code_line(cell.source)
                print("\n" + "-" * 78)
                print(
                    f"CELL {execution_count}/{code_total} "
                    f"(notebook index {cell_index}): {description}"
                )
                cell_started = time.perf_counter()
                try:
                    client.execute_cell(
                        cell,
                        cell_index,
                        execution_count=execution_count,
                    )
                except CellExecutionError:
                    print_cell_outputs(cell)
                    print(f"\nFAILED at cell {execution_count}/{code_total}.")
                    raise
                print_cell_outputs(cell)
                elapsed = time.perf_counter() - cell_started
                print(f"[cell completed in {elapsed:.1f}s]")
    except KeyboardInterrupt:
        print("\nExecution cancelled by user.")
        raise SystemExit(130)
    except CellExecutionError:
        print("The database is not certified ready because the notebook failed.")
        raise SystemExit(1)

    total_elapsed = time.perf_counter() - started
    print("\n" + "=" * 78)
    print(f"NOTEBOOK COMPLETED: {execution_count}/{code_total} code cells in {total_elapsed:.1f}s")
    return notebook, execution_count


def verify_database(database_path: Path) -> list[tuple[str, int]]:
    if not database_path.exists():
        print(f"ERROR: Expected database was not created: {database_path}")
        raise SystemExit(1)

    try:
        import duckdb
    except ModuleNotFoundError as exc:
        print("ERROR: DuckDB is unavailable after notebook execution.")
        raise SystemExit(2) from exc

    with duckdb.connect(str(database_path), read_only=True) as connection:
        table_names = [
            row[0]
            for row in connection.execute("SHOW TABLES").fetchall()
        ]
        if not table_names:
            print(f"ERROR: Database exists but contains no tables: {database_path}")
            raise SystemExit(1)
        counts = [
            (
                table,
                connection.execute(
                    f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34) * 2)}"'
                ).fetchone()[0],
            )
            for table in table_names
        ]
    return counts


def resolve_cli_path(value: Path, project_dir: Path) -> Path:
    return value.resolve() if value.is_absolute() else (project_dir / value).resolve()


def main() -> int:
    configure_terminal()
    project_dir = Path(__file__).resolve().parent
    args = parse_args(project_dir)
    notebook_path = resolve_cli_path(args.notebook, project_dir)
    database_path = resolve_cli_path(args.database, project_dir)

    if not notebook_path.is_file():
        print(f"ERROR: Notebook not found: {notebook_path}")
        return 2

    executed_notebook, _ = execute_notebook(
        notebook_path=notebook_path,
        project_dir=project_dir,
        timeout=args.timeout,
    )

    if args.save_executed:
        nbformat, _, _ = require_notebook_dependencies()
        output_path = resolve_cli_path(Path(args.save_executed), project_dir)
        nbformat.write(executed_notebook, output_path)
        print(f"Executed notebook saved: {output_path}")

    table_counts = verify_database(database_path)
    print("\nDATABASE TABLES")
    for table, count in table_counts:
        print(f"  {table:<30} {count:>10,} rows")

    print("\n" + "=" * 78)
    print("DATABASE READY")
    print(f"File: {database_path}")
    print(f"Size: {database_path.stat().st_size / (1024 * 1024):,.2f} MB")
    print(f"Tables: {len(table_counts)}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
