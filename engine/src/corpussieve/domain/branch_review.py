from datetime import UTC, datetime

from corpussieve.contracts.branch import BranchReviewResult
from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.enums import BranchDecision
from corpussieve.domain.definition import domain_hash
from corpussieve.domain.prompts.branch_v1 import (
    BRANCH_REVIEW_SYSTEM_PROMPT,
)
from corpussieve.domain.traverse import AmbiguousBranchContext
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.models.base import ModelProvider


class LlmAmbiguousHook:
    """Ambiguous branch hook backed by LLM provider and SQLite decision cache."""

    def __init__(
        self,
        provider: ModelProvider,
        model_id: str,
        index: MetadataIndex,
        defn: DomainDefinition,
        source_fingerprint: str,
    ) -> None:
        self.provider = provider
        self.model_id = model_id
        self.index = index
        self.defn = defn
        self.d_hash = domain_hash(defn)
        self.source_fingerprint = source_fingerprint

    def __call__(self, ctx: AmbiguousBranchContext) -> BranchDecision:
        category = ctx.candidate

        # 1. Look up in SQLite decision cache first (Lock Reproducibility Rule)
        cached_list = self.index.get_domain_decisions(self.d_hash, self.source_fingerprint)
        for item in cached_list:
            if item.get("category") == category:
                c_dec = str(item.get("decision", ""))
                if c_dec in ("include", "exclude", "review"):
                    return BranchDecision(c_dec)

        # 2. Bounded context from AmbiguousBranchContext
        children = ctx.sample_children[:10]
        members = ctx.sample_members[:10]

        prompt = (
            f"Domain Name: {self.defn.name}\n"
            f"Domain Description: {self.defn.description}\n"
            f"Root Category: {ctx.root.query}\n"
            f"Parent Path: {' -> '.join(ctx.parent_path)}\n"
            f"Candidate Category: {category}\n"
            f"Sample Child Categories: {', '.join(children) or 'None'}\n"
            f"Sample Member Pages: {', '.join(members) or 'None'}\n\n"
            "Evaluate candidate category inclusion."
        )

        now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")

        try:
            res = self.provider.complete_structured(
                model_id=self.model_id,
                schema=BranchReviewResult,
                system=BRANCH_REVIEW_SYSTEM_PROMPT,
                prompt=prompt,
                max_retries=1,
            )

            if isinstance(res, BranchReviewResult):
                final_decision_str = res.decision
                if res.confidence < 0.7 or res.needs_human_review:
                    final_decision_str = "review"

                b_decision = BranchDecision(final_decision_str)
                self.index.record_domain_decision(
                    domain_hash=self.d_hash,
                    source_fingerprint=self.source_fingerprint,
                    category=category,
                    decision=b_decision,
                    confidence=res.confidence,
                    reason=res.reason or "LLM classification",
                    root=ctx.root.query,
                    depth=len(ctx.parent_path),
                    source="llm",
                    decision_at=now_iso,
                )
                return b_decision

        except Exception as err:
            # Fallback fail-closed to review
            self.index.record_domain_decision(
                domain_hash=self.d_hash,
                source_fingerprint=self.source_fingerprint,
                category=category,
                decision=BranchDecision.REVIEW,
                confidence=0.0,
                reason=f"LLM call error: {err}",
                root=ctx.root.query,
                depth=len(ctx.parent_path),
                source="llm",
                decision_at=now_iso,
            )
            return BranchDecision.REVIEW

        return BranchDecision.REVIEW
