from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from app.domain.linkedin.enums import LinkedInPageKind

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class NavigationResult:
    requested_url: str
    final_url: str
    page_kind: LinkedInPageKind
    loaded: bool
    warnings: tuple[str, ...] = ()
    elapsed_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class ParserResult[T]:
    value: T | None = None
    items: tuple[T, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[object, ...] = ()
    selectors_used: tuple[str, ...] = ()
    is_partial: bool = False
    elapsed_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class ParserLimits:
    experiences: int = 3
    educations: int = 50
    skills: int = 300
    certifications: int = 100
    languages: int = 50


@dataclass(frozen=True, slots=True)
class SectionPlan:
    sections: tuple[str, ...]
    limits: ParserLimits


@dataclass(frozen=True, slots=True)
class SelectorMetadata:
    key: str
    selector: str
    confidence: float
