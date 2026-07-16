"""Command-line interface for ReBT-Rank.

A Typer application exposed as the console script ``rebt-rank`` (see
``[project.scripts]`` in ``pyproject.toml``). Task A1 provides only the
entry-point stub: ``rebt-rank --help`` and ``rebt-rank --version`` work, and the
app is wired for the subcommands (benchmark, candidates, features, train,
calibrate, evaluate, report, run, repro, verify) that later tasks register.
"""

from __future__ import annotations

import typer

from rebt_rank import __version__

app = typer.Typer(
    name="rebt-rank",
    help=(
        "ReBT-Rank: calibrated, FDR-controlled re-ranking of "
        "reverse-biotransformation-derived metabolite-gene hypotheses."
    ),
    add_completion=False,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"rebt-rank {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the ReBT-Rank version and exit.",
    ),
) -> None:
    """ReBT-Rank command-line interface.

    Subcommands are registered by later tasks in the frozen task graph.
    """


def main() -> None:
    """Console-script entry point referenced by ``[project.scripts]``."""
    app()


if __name__ == "__main__":
    main()
