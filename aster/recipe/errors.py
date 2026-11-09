"""Errors raised while selecting and configuring a deployment recipe."""

from aster.core.errors import AsterError


class RecipeConfigError(AsterError):
    """Raised when a recipe's environment or YAML config is invalid."""
