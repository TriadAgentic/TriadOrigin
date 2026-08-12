"""Deterministic, read-only E00-E10 scorecard projection."""

from .builder import SCORECARD_CLAIM, SCORECARD_SCHEMA, build_scorecard
from .codec import INPUT_SCHEMA, build_scorecard_from_dict
from .render import render_scorecard_html, verify_report_digest

__all__ = (
    "INPUT_SCHEMA",
    "SCORECARD_CLAIM",
    "SCORECARD_SCHEMA",
    "build_scorecard",
    "build_scorecard_from_dict",
    "render_scorecard_html",
    "verify_report_digest",
)
