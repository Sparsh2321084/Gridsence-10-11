"""Compatibility exports; implementation lives in :mod:`Web.Backend.storage`."""

from Web.Backend.storage.actuals_store import ActualLoadStore, InferenceHistoryError

__all__ = ["ActualLoadStore", "InferenceHistoryError"]
