"""Errors that carry a human message (and optional per-field messages) to the frontend."""


class FieldError(Exception):
    def __init__(self, status: int, message: str, fields: dict[str, str] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.fields = fields or {}
