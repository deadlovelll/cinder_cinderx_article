"""Selling region. A small fixed set, so availability is a bitmask on the read path."""

from enum import Enum


class Region(Enum):
    EU = "eu"
    US = "us"
    APAC = "apac"
