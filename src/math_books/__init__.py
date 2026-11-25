"""Math_books package: STEM-Basketball vertical videos and math book digitization."""


def main(argv: list[str] | None = None) -> None:
    """Load the CLI on invocation, keeping low-level imports independent."""
    from math_books.cli import main as cli_main

    cli_main(argv)


__all__ = ["main"]
