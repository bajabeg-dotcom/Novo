class SmfError(ValueError):
    """Base class for controlled SMF parsing and serialization errors."""

    def __init__(self, message: str, *, offset: int | None = None, context: str | None = None) -> None:
        self.message = message
        self.offset = offset
        self.context = context
        details = message
        if offset is not None:
            details += f" at byte {offset}"
        if context:
            details += f" ({context})"
        super().__init__(details)


class SmfStructureError(SmfError):
    pass


class PreserveMismatchError(SmfError):
    """Raised when strict preserve output is requested after semantic changes."""