from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationResult:
    """Result returned by service-layer validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, warnings: list[str] | None = None) -> "ValidationResult":
        return cls(valid=True, warnings=list(warnings or []))

    @classmethod
    def invalid(
        cls,
        errors: list[str],
        warnings: list[str] | None = None,
    ) -> "ValidationResult":
        return cls(valid=False, errors=list(errors), warnings=list(warnings or []))
