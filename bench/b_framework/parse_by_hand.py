from __future__ import annotations

from bench.b_framework.constants import MAX_CANDIDATES, MAX_LIMIT
from bench.b_framework.hand_validation_error import HandValidationError


def parse_by_hand(body):
    """The service's previous validator, field for field."""
    if not isinstance(body, dict):
        raise HandValidationError("body")
    user_id = body.get("user_id")
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise HandValidationError("user_id")
    limit = body.get("limit", 20)
    if (not isinstance(limit, int) or isinstance(limit, bool)
            or not 1 <= limit <= MAX_LIMIT):
        raise HandValidationError("limit")
    candidates = body.get("candidate_limit", 400)
    if (not isinstance(candidates, int) or isinstance(candidates, bool)
            or not limit <= candidates <= MAX_CANDIDATES):
        raise HandValidationError("candidate_limit")
    return user_id, limit, candidates
