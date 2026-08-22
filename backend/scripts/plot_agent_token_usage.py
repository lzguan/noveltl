import argparse
import html
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = REPO_ROOT / "tmp" / "runs" / "snake"


@dataclass(frozen=True)
class ChapterUsage:
    chapter_num: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int

    @property
    def uncached_input_tokens(self) -> int:
        return max(0, self.input_tokens - self.cache_read_tokens)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _latest_run(runs_dir: Path) -> Path:
    candidates = [
        path for path in runs_dir.iterdir() if path.is_dir() and any((path / "chapters").glob("chapter-*.json"))
    ]
    if not candidates:
        raise ValueError(f"No runs with chapter artifacts found in {runs_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _required_int(mapping: dict[str, Any], key: str, source: Path) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{source}: {key} must be a non-negative integer")
    return value


def _load_usage(run_dir: Path) -> list[ChapterUsage]:
    chapter_dir = run_dir / "chapters"
    chapter_files = sorted(chapter_dir.glob("chapter-*.json"))
    if not chapter_files:
        raise ValueError(f"No chapter artifacts found in {chapter_dir}")

    chapters: list[ChapterUsage] = []
    for source in chapter_files:
        with source.open(encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict) or not isinstance(payload.get("usage"), dict):
            raise ValueError(f"{source}: expected an object containing usage data")
        usage = payload["usage"]
        chapters.append(
            ChapterUsage(
                chapter_num=_required_int(payload, "chapterNum", source),
                input_tokens=_required_int(usage, "inputTokens", source),
                output_tokens=_required_int(usage, "outputTokens", source),
                cache_read_tokens=_required_int(usage, "cacheReadTokens", source),
            )
        )

    chapters.sort(key=lambda chapter: chapter.chapter_num)
    return chapters


def _nice_axis_max(value: int) -> int:
    if value <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(value))
    normalized = value / magnitude
    step = 1 if normalized <= 1 else 2 if normalized <= 2 else 5 if normalized <= 5 else 10
    return step * magnitude


def _format_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}k"
    return str(value)


def _render_svg(chapters: list[ChapterUsage], run_name: str) -> str:
    width = 1280
    height = 720
    left = 90
    right = 36
    top = 100
    bottom = 90
    chart_width = width - left - right
    chart_height = height - top - bottom
    axis_max = _nice_axis_max(max(chapter.total_tokens for chapter in chapters))
    slot_width = chart_width / len(chapters)
    bar_width = max(2.0, min(20.0, slot_width * 0.72))
    label_every = max(1, math.ceil(len(chapters) / 16))

    total_input = sum(chapter.input_tokens for chapter in chapters)
    total_output = sum(chapter.output_tokens for chapter in chapters)
    total_cache = sum(chapter.cache_read_tokens for chapter in chapters)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">',
        "<style>",
        "text { font-family: ui-sans-serif, system-ui, sans-serif; fill: #263238; }",
        ".grid { stroke: #d9e0e3; stroke-width: 1; }",
        ".axis { stroke: #546e7a; stroke-width: 1.5; }",
        ".tick { font-size: 12px; }",
        ".legend { font-size: 13px; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fafcfd"/>',
        f'<text x="{left}" y="36" font-size="23" font-weight="600">Token usage per chapter</text>',
        f'<text x="{left}" y="61" font-size="13">Run: {html.escape(run_name)}</text>',
        f'<text x="{left}" y="80" font-size="13">{len(chapters)} completed chapters · '
        f"{_format_tokens(total_input + total_output)} total · "
        f"{_format_tokens(total_cache)} cache-read input</text>",
    ]

    legend = [
        ("#4472c4", "Cache-read input"),
        ("#ed7d31", "Uncached input"),
        ("#70ad47", "Output"),
    ]
    legend_x = width - right - 420
    for index, (color, label) in enumerate(legend):
        x = legend_x + index * 140
        parts.append(f'<rect x="{x}" y="27" width="12" height="12" rx="2" fill="{color}"/>')
        parts.append(f'<text class="legend" x="{x + 18}" y="38">{label}</text>')

    for tick in range(6):
        value = axis_max * tick / 5
        y = top + chart_height - chart_height * tick / 5
        parts.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}"/>')
        parts.append(
            f'<text class="tick" x="{left - 12}" y="{y + 4:.1f}" text-anchor="end">'
            f"{_format_tokens(round(value))}</text>"
        )

    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_height}"/>')
    parts.append(
        f'<line class="axis" x1="{left}" y1="{top + chart_height}" x2="{width - right}" y2="{top + chart_height}"/>'
    )

    colors = ("#4472c4", "#ed7d31", "#70ad47")
    for index, chapter in enumerate(chapters):
        x = left + index * slot_width + (slot_width - bar_width) / 2
        values = (
            chapter.cache_read_tokens,
            chapter.uncached_input_tokens,
            chapter.output_tokens,
        )
        y_bottom = top + chart_height
        parts.append(f"<g><title>Chapter {chapter.chapter_num}: {chapter.total_tokens:,} total tokens</title>")
        for value, color in zip(values, colors, strict=True):
            segment_height = chart_height * value / axis_max
            y_bottom -= segment_height
            parts.append(
                f'<rect x="{x:.2f}" y="{y_bottom:.2f}" width="{bar_width:.2f}" '
                f'height="{segment_height:.2f}" fill="{color}"/>'
            )
        parts.append("</g>")
        if index % label_every == 0 or index == len(chapters) - 1:
            label_x = x + bar_width / 2
            parts.append(
                f'<text class="tick" x="{label_x:.2f}" y="{top + chart_height + 23}" '
                f'text-anchor="middle">{chapter.chapter_num}</text>'
            )

    parts.append(
        f'<text x="{left + chart_width / 2:.1f}" y="{height - 26}" font-size="14" text-anchor="middle">Chapter</text>'
    )
    parts.append(
        f'<text x="22" y="{top + chart_height / 2:.1f}" font-size="14" '
        f'text-anchor="middle" transform="rotate(-90 22 {top + chart_height / 2:.1f})">Tokens</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an SVG chart from memory-agent chapter run artifacts.")
    parser.add_argument(
        "run_dir",
        nargs="?",
        type=Path,
        help=f"Run directory (default: latest run under {DEFAULT_RUNS_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output SVG path (default: <run-dir>/token-usage.svg)",
    )
    args = parser.parse_args()

    try:
        run_dir = args.run_dir or _latest_run(DEFAULT_RUNS_DIR)
        chapters = _load_usage(run_dir)
        output = args.output or run_dir / "token-usage.svg"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(_render_svg(chapters, run_dir.name), encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(f"Plotted {len(chapters)} chapter(s) to {output}.")


if __name__ == "__main__":
    main()
