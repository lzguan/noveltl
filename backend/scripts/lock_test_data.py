import argparse
import sys
from pathlib import Path

from test_support.test_data.errors import TestDataError
from test_support.test_data.lockfile import check_lock, write_lock


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate or verify a test-data catalog lock.")
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("targets", nargs="*", help="Folders relative to the dataset root.")
    parser.add_argument("--all", action="store_true", help="Process the complete catalog and prune stale entries.")
    parser.add_argument("--check", action="store_true", help="Verify without writing the lockfile.")
    args = parser.parse_args()
    if args.all and args.targets:
        parser.error("targets and --all are mutually exclusive")
    if not args.all and not args.targets:
        parser.error("provide one or more targets or use --all")
    targets = None if args.all else args.targets
    try:
        if args.check:
            check_lock(args.dataset_root, targets)
            print(f"Lock is current: {args.dataset_root}")
        else:
            write_lock(args.dataset_root, targets)
            print(f"Updated lock: {args.dataset_root / 'catalog.lock.json'}")
    except TestDataError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
