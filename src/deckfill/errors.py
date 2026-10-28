"""Error types. Each carries a short code the page maps to a plain message."""


class DeckfillError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class TemplateError(DeckfillError):
    """The template cannot be used. Codes: legacy_ppt, encrypted, not_pptx, bad_file,
    too_big, no_text_layout."""


class OutlineError(DeckfillError):
    """The outline cannot be planned. Codes: too_long, no_slides."""


class PlanError(DeckfillError):
    """A plan cannot be made or used. Codes: too_many_slides, incompatible_layout,
    unknown_layout, stale_plan."""
