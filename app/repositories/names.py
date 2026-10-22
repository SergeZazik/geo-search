"""Fuzzy search by name with pg_trgm, the same way for places, streets and admin areas."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, func, or_
from sqlalchemy.orm import InstrumentedAttribute


def name_matches(phrase: str, columns: Sequence[InstrumentedAttribute[Any]]) -> ColumnElement[bool]:
    # name %> phrase means word_similarity(phrase, name) >= 0.6 (the pg_trgm default):
    # the phrase is compared with the best-matching part of the name, so
    # "набережная" finds "Січеславська набережна". With the column on the left,
    # the table's names_trgm GIN index serves the condition.
    return or_(*(column.op("%>", is_comparison=True)(phrase) for column in columns))


def name_similarity(
    phrase: str, columns: Sequence[InstrumentedAttribute[Any]]
) -> ColumnElement[float]:
    # GREATEST skips NULLs, so a missing translation does not hide a match.
    return func.greatest(*(func.word_similarity(phrase, column) for column in columns))
