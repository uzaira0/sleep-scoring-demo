"""
Nonwear detection algorithm implementations.

This package contains implementations of nonwear detection algorithms.
All algorithms implement the NonwearDetectionAlgorithm protocol.

Algorithms:
    - ChoiAlgorithm: Choi et al. (2011) - 90-minute window algorithm
    - VanHeesNonwearAlgorithm: van Hees et al. (2023) - SD/range-based algorithm

Exports:
    - ChoiAlgorithm: Class implementing Choi algorithm
    - VanHeesNonwearAlgorithm: Class implementing van Hees algorithm

"""

from __future__ import annotations

from .choi import ChoiAlgorithm
from .factory import NonwearAlgorithmFactory
from .protocol import NonwearDetectionAlgorithm
from .van_hees import VanHeesNonwearAlgorithm

__all__ = [
    # Algorithm classes
    "ChoiAlgorithm",
    # Factory
    "NonwearAlgorithmFactory",
    # Protocol
    "NonwearDetectionAlgorithm",
    "VanHeesNonwearAlgorithm",
]
