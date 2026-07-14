from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IdentityChange:
    field: str
    old_value: object
    new_value: object
    action: str
    reason: str
    confidence: float


@dataclass(frozen=True, slots=True)
class CollectionDiff:
    section: str
    create_count: int = 0
    update_count: int = 0
    delete_count: int = 0
    unchanged_count: int = 0
    conflicts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateEnrichmentDiff:
    identity_changes: tuple[IdentityChange, ...]
    experiences: CollectionDiff
    educations: CollectionDiff
    skills: CollectionDiff
    certifications: CollectionDiff
    languages: CollectionDiff
    predicted_quality_before: float
    predicted_quality_after: float
    warnings: tuple[str, ...] = ()
