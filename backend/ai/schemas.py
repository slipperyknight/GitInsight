"""Structured-output schemas for AI enrichment.

These Pydantic models are passed to `client.messages.parse(output_format=...)` so Claude
returns enum-constrained JSON that maps directly onto the `ai_*` columns. Defined once and
reused for both the parse call and downstream typing.

Schema mirrors CLAUDE.md "Structured output schema for PR impact reads" exactly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "Feature", "BugFix", "Refactor", "Infrastructure", "Security", "Documentation"
]
Scope = Literal["trivial", "small", "moderate", "substantial", "major"]
Risk = Literal["low", "medium", "high"]


class CommitCategory(BaseModel):
    """Per-commit, message-only categorization (Haiku). Powers the timeline."""

    category: Category
    summary: str = Field(description="One short human-readable sentence about the commit.")


class PRImpact(BaseModel):
    """Per-merged-PR impact read from the diff (Sonnet). Populates the ai_* columns."""

    category: Category
    scope: Scope
    risk: Risk
    surfaces: list[str] = Field(
        description="Subsystems/modules touched, e.g. ['billing', 'auth']."
    )
    has_tests: bool
    impact_summary: str = Field(
        description="One sentence. Triple-use: metric input, drill-down receipt, summary feed."
    )
