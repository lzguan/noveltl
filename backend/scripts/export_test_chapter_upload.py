import argparse
import sys
from pathlib import Path

from src.datasets.errors import TestDataError
from test_support.test_data.exporting import export_chapter_upload


def _content_version(value: str) -> int | None:
    if value == "latest":
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("content version must be latest or a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("content version must be latest or a positive integer")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a cataloged test novel as a bulk chapter upload document.")
    parser.add_argument("dataset_dir", type=Path, help="Directory containing catalog.json.")
    parser.add_argument("novel_id")
    parser.add_argument("output_file", type=Path)
    parser.add_argument("--format", choices=["v1"], default="v1", dest="format_version")
    parser.add_argument(
        "--content-version",
        type=_content_version,
        default=None,
        metavar="latest|N",
        help="Chapter content version to export (default: latest).",
    )
    args = parser.parse_args()
    try:
        count = export_chapter_upload(
            args.dataset_dir,
            args.novel_id,
            args.output_file,
            format_version=args.format_version,
            content_version=args.content_version,
        )
    except (OSError, TestDataError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    print(f"Exported {count} chapter(s) to {args.output_file}.")


if __name__ == "__main__":
    main()
