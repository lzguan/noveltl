import argparse
import sys
from pathlib import Path

from test_support.test_data.authoring import add_novel
from test_support.test_data.errors import TestDataError


def main() -> None:
    parser = argparse.ArgumentParser(description="Add plaintext chapters as a novel in a test-data catalog.")
    parser.add_argument("data_to_insert_dir", type=Path)
    parser.add_argument("catalog_dir", type=Path)
    parser.add_argument("--no-id", action="store_true", help="Generate the novel ID from its title.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing files.")
    args = parser.parse_args()
    try:
        novel_id = add_novel(args.data_to_insert_dir, args.catalog_dir, no_id=args.no_id, dry_run=args.dry_run)
    except TestDataError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    action = "Would add" if args.dry_run else "Added"
    print(f"{action} novel: {novel_id}")


if __name__ == "__main__":
    main()
