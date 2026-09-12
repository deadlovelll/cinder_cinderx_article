"""Behavioural segment. Chooses which weights the ranker applies."""

from enum import Enum


class Segment(Enum):
    NEW = "new"
    CASUAL = "casual"
    LOYAL = "loyal"
    BARGAIN = "bargain"
