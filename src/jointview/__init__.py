"""Explore the joint distribution of two Polars DataFrame columns."""

from jointview.data import demo_frame, load_frame
from jointview.plot import default_pair, encoding_type, joint_chart, joint_frame

__all__ = [
    "default_pair",
    "demo_frame",
    "encoding_type",
    "joint_chart",
    "joint_frame",
    "load_frame",
]
