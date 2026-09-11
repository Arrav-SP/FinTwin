from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class Scenario(StrEnum):
    NORMAL_DAY = "NORMAL_DAY"
    SALARY_DAY = "SALARY_DAY"
    MONTH_END = "MONTH_END"
    FESTIVAL_SPIKE = "FESTIVAL_SPIKE"
    CARD_PAYMENT_SPIKE = "CARD_PAYMENT_SPIKE"
    LOAN_PROCESSING = "LOAN_PROCESSING"
    HIGH_CONCURRENCY_TRANSFER = "HIGH_CONCURRENCY_TRANSFER"


OperationMix = Mapping[str, float]

DEFAULT_MIXES: dict[Scenario, dict[str, float]] = {
    Scenario.NORMAL_DAY: {"BALANCE_CHECK": 0.35, "RECENT_TRANSACTIONS": 0.20, "TRANSFER": 0.20, "DEPOSIT": 0.10, "WITHDRAWAL": 0.10, "PAYMENT": 0.05},
    Scenario.SALARY_DAY: {"DEPOSIT": 0.35, "BALANCE_CHECK": 0.25, "TRANSFER": 0.20, "RECENT_TRANSACTIONS": 0.10, "PAYMENT": 0.10},
    Scenario.MONTH_END: {"BALANCE_CHECK": 0.20, "RECENT_TRANSACTIONS": 0.20, "LOAN_PROCESSING": 0.30, "TRANSFER": 0.15, "PAYMENT": 0.15},
    Scenario.FESTIVAL_SPIKE: {"PAYMENT": 0.40, "BALANCE_CHECK": 0.25, "RECENT_TRANSACTIONS": 0.15, "TRANSFER": 0.10, "DEPOSIT": 0.10},
    Scenario.CARD_PAYMENT_SPIKE: {"PAYMENT": 0.60, "BALANCE_CHECK": 0.20, "RECENT_TRANSACTIONS": 0.15, "TRANSFER": 0.05},
    Scenario.LOAN_PROCESSING: {"LOAN_PROCESSING": 0.55, "BALANCE_CHECK": 0.20, "TRANSFER": 0.10, "DEPOSIT": 0.10, "RECENT_TRANSACTIONS": 0.05},
    Scenario.HIGH_CONCURRENCY_TRANSFER: {"TRANSFER": 0.70, "BALANCE_CHECK": 0.15, "RECENT_TRANSACTIONS": 0.10, "PAYMENT": 0.05},
}


@dataclass(frozen=True)
class WorkloadConfig:
    scenario: Scenario = Scenario.NORMAL_DAY
    concurrency: int = 4
    target_tps: float = 10.0
    duration_seconds: float = 10.0
    operation_mix: OperationMix | None = None
    seed: int = 42
    burstiness: float = 0.0

    def __post_init__(self) -> None:
        if self.concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if self.target_tps <= 0:
            raise ValueError("target_tps must be greater than 0")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be greater than 0")
        if not 0 <= self.burstiness <= 1:
            raise ValueError("burstiness must be between 0 and 1")
        mix = dict(self.operation_mix or DEFAULT_MIXES[self.scenario])
        if not mix or any(weight <= 0 for weight in mix.values()):
            raise ValueError("operation_mix must contain positive weights")
        if abs(sum(mix.values()) - 1.0) > 1e-6:
            raise ValueError("operation_mix weights must sum to 1")
        object.__setattr__(self, "operation_mix", mix)

