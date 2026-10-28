"""deckfill: fill a company PowerPoint template from a plain-text outline.

Public interface (spec D1): read_template, parse_outline, plan_deck, fill.
"""

from .errors import DeckfillError, OutlineError, PlanError, TemplateError
from .fill import fill
from .outline import Item, Outline, OutlineSlide, Warning, parse_outline
from .plan import Plan, PlannedSlide, plan_deck
from .template import TemplateInfo, read_template

__all__ = [
    "DeckfillError",
    "Item",
    "Outline",
    "OutlineError",
    "OutlineSlide",
    "Plan",
    "PlanError",
    "PlannedSlide",
    "TemplateError",
    "TemplateInfo",
    "Warning",
    "fill",
    "parse_outline",
    "plan_deck",
    "read_template",
]
