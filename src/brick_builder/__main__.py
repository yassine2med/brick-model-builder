"""Command line: python -m brick_builder SHEET.csv [--out model.ttl]."""
from __future__ import annotations

import argparse
import sys

from .core import ModelError, count_triples, read_entities, to_turtle


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="brick_builder", description="Equipment CSV to Brick Turtle")
    parser.add_argument("csv")
    parser.add_argument("--out", help="write Turtle here instead of printing it")
    args = parser.parse_args(argv)
    try:
        entities = read_entities(args.csv)
        turtle = to_turtle(entities)
        triples = count_triples(turtle)
    except ModelError as exc:
        print("model has problems:\n" + str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # unreadable file or Turtle that rdflib rejects
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(turtle)
    else:
        print(turtle, end="")
    print(f"{len(entities)} entities, {triples} triples, parsed by rdflib", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
