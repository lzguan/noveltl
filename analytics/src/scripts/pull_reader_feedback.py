import argparse
import gzip
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config

KIND = "reader_feedback.v1"
DEFAULT_API_URL = "http://localhost:8001"
DEFAULT_BUCKET = "analytics"


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
        region_name=os.environ.get("S3_REGION"),
        config=Config(s3={"addressing_style": os.environ.get("S3_ADDRESSING_STYLE", "auto")}),
    )


def _login_for_token(api_url: str, username: str, password: str, timeout: float) -> str:
    body = json.dumps({"username": username, "password": password}).encode()
    req = Request(
        f"{api_url}/admin/login",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    token = payload.get("accessToken")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Reader API /admin/login response missing accessToken")
    return token


def _export_feedback(
    api_url: str,
    token: str,
    since: str | None,
    until: str | None,
    timeout: float,
) -> tuple[bytes, str]:
    params: dict[str, str] = {}
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    query = f"?{urlencode(params)}" if params else ""
    req = Request(
        f"{api_url}/admin/feedback/export{query}",
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/x-ndjson",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        export_until = resp.headers.get("X-Export-Until") or until or datetime.now(UTC).isoformat()
        return raw, export_until


def _format_until_slug(export_until: str) -> str:
    try:
        parsed = datetime.fromisoformat(export_until.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    except ValueError:
        return "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in export_until)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pull reader feedback NDJSON from reader-api and write locally or upload to S3."
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("READER_API_URL", DEFAULT_API_URL),
        help="Base URL of reader-api (default: READER_API_URL or http://localhost:8001)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("READER_ADMIN_TOKEN", ""),
        help="Admin bearer token (default: READER_ADMIN_TOKEN)",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("READER_ADMIN_USERNAME", ""),
        help="Admin username for /admin/login when --token is not given",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("READER_ADMIN_PASSWORD", ""),
        help="Admin password for /admin/login when --token is not given",
    )
    parser.add_argument("--since", default=None, help="Exclusive lower bound ISO timestamp")
    parser.add_argument("--until", default=None, help="Inclusive upper bound ISO timestamp")
    parser.add_argument(
        "--bucket",
        default=os.environ.get("ANALYTICS_BUCKET", DEFAULT_BUCKET),
        help="Target S3 bucket (default: ANALYTICS_BUCKET or analytics)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write export to a local path instead of uploading to S3 (.gz writes gzipped NDJSON)",
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP request timeout in seconds")

    args = parser.parse_args(argv)
    api_url = args.api_url.rstrip("/")

    token = args.token.strip()
    if not token:
        if not args.username or not args.password:
            parser.error("Provide --token or both --username and --password.")
        try:
            token = _login_for_token(api_url, args.username, args.password, args.timeout)
        except (HTTPError, URLError, RuntimeError) as exc:
            print(f"Failed to authenticate with {api_url}: {exc}", file=sys.stderr)
            return 1

    try:
        ndjson_bytes, export_until = _export_feedback(api_url, token, args.since, args.until, args.timeout)
    except (HTTPError, URLError) as exc:
        print(f"Failed to export feedback from {api_url}: {exc}", file=sys.stderr)
        return 1

    row_count = sum(1 for line in ndjson_bytes.splitlines() if line.strip())

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix == ".gz":
            output_path.write_bytes(gzip.compress(ndjson_bytes))
        else:
            output_path.write_bytes(ndjson_bytes)
        print(f"wrote {row_count} row(s) to {output_path} (until={export_until})")
        return 0

    if row_count == 0:
        print(f"no new feedback rows to upload (until={export_until})")
        return 0

    slug = _format_until_slug(export_until)
    key = f"exports/{KIND}/{slug}.jsonl.gz"
    compressed = gzip.compress(ndjson_bytes)
    _s3_client().put_object(
        Bucket=args.bucket,
        Key=key,
        Body=compressed,
        ContentType="application/x-ndjson",
        ContentEncoding="gzip",
    )
    print(f"uploaded {row_count} row(s) to s3://{args.bucket}/{key} (until={export_until})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
