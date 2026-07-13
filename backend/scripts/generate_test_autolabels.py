import argparse
import sys
from pathlib import Path

from test_support.test_data.authoring import generate_autolabels, parse_chapters
from test_support.test_data.errors import TestDataError


def _version(value: str) -> int | None:
    if value == "latest":
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("version must be latest or a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("version must be latest or a positive integer")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate autolabel artifacts for a cataloged test novel.")
    parser.add_argument("catalog_dir", type=Path)
    parser.add_argument("novel_id")
    parser.add_argument("--config", required=True, dest="config_id")
    parser.add_argument("--chapters", type=parse_chapters)
    parser.add_argument("--version", type=_version, default=None, metavar="latest|N")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate selection without loading the model.")
    args = parser.parse_args()
    try:
        count = generate_autolabels(
            args.catalog_dir,
            args.novel_id,
            args.config_id,
            chapters=args.chapters,
            version=args.version,
            force=args.force,
            dry_run=args.dry_run,
        )
    except (TestDataError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    action = "Would generate" if args.dry_run else "Generated"
    print(f"{action} {count} autolabel artifact(s).")


if __name__ == "__main__":
    main()
