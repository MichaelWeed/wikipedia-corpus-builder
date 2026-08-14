from enum import StrEnum


class JobState(StrEnum):
    NEW = "NEW"
    SOURCE_INSPECTED = "SOURCE_INSPECTED"
    METADATA_INDEXING = "METADATA_INDEXING"
    METADATA_READY = "METADATA_READY"
    DOMAIN_DRAFT = "DOMAIN_DRAFT"
    DOMAIN_COMPILED = "DOMAIN_COMPILED"
    PREVIEWED = "PREVIEWED"
    BUILDING = "BUILDING"
    BUILD_SUCCEEDED = "BUILD_SUCCEEDED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    EXPORTED = "EXPORTED"
    SOURCE_PURGED = "SOURCE_PURGED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SelectionMode(StrEnum):
    HIGH_RECALL = "high_recall"
    BALANCED = "balanced"
    HIGH_PRECISION = "high_precision"


class AmbiguousBranchPolicy(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    REVIEW = "review"


class MemberType(StrEnum):
    PAGE = "page"
    SUBCAT = "subcat"


class BranchDecision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    REVIEW = "review"
