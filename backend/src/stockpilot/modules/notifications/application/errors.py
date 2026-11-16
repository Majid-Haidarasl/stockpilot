"""Application-level consume errors."""


class PermanentConsumeError(Exception):
    """Poison / unknown type / bad envelope — do not retry."""
