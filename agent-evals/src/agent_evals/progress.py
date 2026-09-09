from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

RunStatus = Literal["running", "completed", "failed", "interrupted", "budget_exceeded"]
ProgressKind = Literal[
    "run_started",
    "replica_started",
    "chapter_completed",
    "chapter_failed",
    "replica_finished",
    "run_finished",
]


@dataclass(frozen=True)
class RunProgress:
    kind: ProgressKind
    run_id: str
    run_path: Path
    replica: int | None = None
    chapter_num: int | None = None
    attempt: int | None = None
    status: RunStatus | None = None
    replica_cost_usd: Decimal | None = None
    run_cost_usd: Decimal | None = None
    message: str | None = None
