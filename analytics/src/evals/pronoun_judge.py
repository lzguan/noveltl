import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from ..chapters import chapter_data
from ..connection import connect

OUT_DIR = Path(__file__).resolve().parents[2] / ".data" / "evals"
DEFAULT_JOB = "2e5b8145-9b08-4f9f-a9ae-8bb43d4469c7"  # magical-girl baseline, chapters 1-20
TICS = ("genuinely", "slightly", "faintly", "a hint of")

RUBRIC = """\
You check pronouns in an English translation of a Chinese novel chapter.

Chinese writes 他 for "he" and 她 for "she". The translation must follow the source at every occurrence, even when \
the same character is called 他 in one place and 她 in another: the author does that on purpose.

Report a mismatch only when the translation uses he/him/his/himself for a person the source calls 她 at that point, \
or she/her/hers/herself for a person the source calls 他. Where the source omits the pronoun, judge by how the source \
refers to that character in the surrounding sentences. Do not report anything else: no style, no word choice, no \
other errors. If there are no mismatches, return an empty list.
"""


class Mismatch(BaseModel):
    character: str = Field(description="The character's name as written in the translation.")
    source_pronoun: Literal["他", "她"] = Field(description="The pronoun the source uses for them here.")
    translation_pronoun: str = Field(description="The pronoun the translation used instead.")
    source_quote: str = Field(description="The source sentence, verbatim.")
    translation_quote: str = Field(description="The translated sentence, verbatim.")


class PronounReport(BaseModel):
    mismatches: list[Mismatch] = Field(description="Every pronoun mismatch found; empty if none.")


@dataclass
class ChapterInputs:
    source: str
    translation: str


def _judge_agent() -> Agent[None, PronounReport]:
    return Agent(
        "deepseek:deepseek-v4-flash",
        output_type=PronounReport,
        instructions=RUBRIC,
        model_settings={"extra_body": {"thinking": {"type": "disabled"}}},
    )


@dataclass
class PronounJudge(Evaluator[ChapterInputs, str]):
    async def evaluate(self, ctx: EvaluatorContext[ChapterInputs, str]) -> dict[str, EvaluationReason]:
        prompt = f"SOURCE (Chinese):\n{ctx.inputs.source}\n\nTRANSLATION (English):\n{ctx.output}"
        result = await _judge_agent().run(prompt)
        mismatches = result.output.mismatches
        detail = json.dumps([m.model_dump() for m in mismatches], ensure_ascii=False)
        return {"pronoun_mismatches": EvaluationReason(value=len(mismatches), reason=detail)}


@dataclass
class TicRate(Evaluator[ChapterInputs, str]):
    def evaluate(self, ctx: EvaluatorContext[ChapterInputs, str]) -> dict[str, float]:
        text = ctx.output.lower()
        words = max(len(text.split()), 1)
        return {f"{tic}_per_1k": round(1000 * len(re.findall(rf"\b{tic}\b", text)) / words, 2) for tic in TICS}


def build_dataset(job_ids: list[str], chapters: list[int] | None) -> Dataset[ChapterInputs, str]:
    rows = chapter_data(connect(), job_ids=job_ids, chapters=chapters)
    cases = [
        Case(
            name=f"{str(row.job_id)[:8]}-ch{row.chapter_num}",
            inputs=ChapterInputs(source=row.source, translation=row.output),
            metadata={"job_id": str(row.job_id), "chapter_num": row.chapter_num, "condition": row.condition_hash},
        )
        for row in rows
    ]
    return Dataset(name="pronoun-judge", cases=cases, evaluators=[TicRate(), PronounJudge()])


def _parse_chapters(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    nums: list[int] = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        nums.extend(range(int(lo), int(hi or lo) + 1))
    return nums


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge pronoun fidelity of stored translations.")
    parser.add_argument("--job", action="append", dest="job_ids", help=f"job id (default {DEFAULT_JOB[:8]})")
    parser.add_argument("--chapters", help="e.g. 1-20,200")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        parser.error("DEEPSEEK_API_KEY is not set (try: uv run --env-file ../.env python -m src.evals.pronoun_judge)")

    dataset = build_dataset(args.job_ids or [DEFAULT_JOB], _parse_chapters(args.chapters))
    report = dataset.evaluate_sync(lambda inputs: inputs.translation, max_concurrency=args.concurrency)
    report.print(include_input=False, include_output=False)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"pronoun-judge-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.jsonl"
    with out.open("w") as handle:
        for case in report.cases:
            record = {
                "case": case.name,
                **(case.metadata or {}),
                "scores": {name: result.value for name, result in case.scores.items()},
                "mismatches": json.loads(case.scores["pronoun_mismatches"].reason or "[]")
                if "pronoun_mismatches" in case.scores
                else None,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        for failure in report.failures:
            handle.write(json.dumps({"case": failure.name, "error": failure.error_message}) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
