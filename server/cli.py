"""
JobHunt — CLI Commands

Contains command-line utilities and subcommands for the JobHunt tool.
"""

from rich.console import Console
from rich.table import Table

from server.services.db import Database


def show_stats() -> None:
    """
    Query the database and display a formatted table of draft statuses.
    """
    db = Database()
    try:
        stats = db.get_stats()

        table = Table(title="JobHunt Processing Stats")
        table.add_column("Status", style="cyan", justify="left")
        table.add_column("Count", style="magenta", justify="right")

        # Ensure we always show some common statuses even if 0
        all_statuses = set(stats.keys()).union({"drafted", "skipped", "approved"})

        total = 0
        for status in sorted(all_statuses):
            count = stats.get(status, 0)
            total += count
            table.add_row(status, str(count))

        table.add_section()
        table.add_row("Total Processed", str(total), style="bold")

        console = Console()
        console.print()
        console.print(table)
        console.print()
    finally:
        db.close()
