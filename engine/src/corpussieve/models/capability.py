from typing import Literal

from pydantic import BaseModel, Field

from corpussieve.models.base import CapabilityResult, ModelProvider
from corpussieve.models.prompts.capability_v1 import CAPABILITY_TEST_CASES


class BranchTestOutput(BaseModel):
    decision: Literal["include", "exclude", "review"] = Field(description="Branch decision")
    reason: str = Field(description="Explanation for decision")


def run_capability_test(provider: ModelProvider, model_id: str) -> CapabilityResult:
    """Run standard 3-prompt capability test on target model."""
    passed_count = 0
    details: list[str] = []

    for idx, test_case in enumerate(CAPABILITY_TEST_CASES, start=1):
        try:
            res = provider.complete_structured(
                model_id=model_id,
                schema=BranchTestOutput,
                system=test_case["system"],
                prompt=test_case["prompt"],
                max_retries=1,
            )
            if isinstance(res, BranchTestOutput) and res.decision == test_case["expected"]:
                passed_count += 1
                details.append(f"Test {idx}: Passed ({res.decision})")
            else:
                act = getattr(res, "decision", str(res))
                details.append(f"Test {idx}: Failed (Expected {test_case['expected']}, got {act})")
        except Exception as e:
            details.append(f"Test {idx}: Error ({e})")

    if passed_count == 3:
        status: Literal["passed", "warn", "failed"] = "passed"
    elif passed_count == 2:
        status = "warn"
    else:
        status = "failed"

    return CapabilityResult(
        provider=provider.endpoint.provider,
        model_id=model_id,
        status=status,
        score=f"{passed_count}/3",
        details=details,
    )
