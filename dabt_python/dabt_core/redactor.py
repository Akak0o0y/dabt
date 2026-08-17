"""Offset-preserving text redaction with deterministic overlapping-span handling."""

from __future__ import annotations

from .obligations import RedactionObligation


def _merge(obligations: list[RedactionObligation]) -> list[RedactionObligation]:
    if not obligations:
        return []
    ordered = sorted(obligations, key=lambda item: (item.start, item.end))
    merged: list[RedactionObligation] = [ordered[0]]
    for item in ordered[1:]:
        previous = merged[-1]
        if item.start <= previous.end:
            merged[-1] = RedactionObligation(
                previous.start,
                max(previous.end, item.end),
                previous.category,
                "full" if "full" in {previous.strategy, item.strategy} else previous.strategy,
            )
        else:
            merged.append(item)
    return merged


def _mask(value: str, strategy: str) -> str:
    if strategy == "last_four" and len(value) > 4:
        return "█" * (len(value) - 4) + value[-4:]
    return "█" * len(value)


def apply_redactions(text: str, obligations: tuple[RedactionObligation, ...] | list[RedactionObligation]) -> str:
    """Mask source spans while retaining text length and all unrelated content."""
    output = text
    for obligation in reversed(_merge(list(obligations))):
        start = max(0, obligation.start)
        end = min(len(output), obligation.end)
        if start >= end:
            continue
        output = output[:start] + _mask(output[start:end], obligation.strategy) + output[end:]
    return output
