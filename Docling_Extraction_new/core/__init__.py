"""
RegScan-V2 Core Components
========================

Core components for the RegScan-V2 multi-document RAG-based extraction system.
"""

from .config_loader import ConfigLoader  # Core configuration
from .logger import Logger               # Logging interface

__all__ = [
    'ConfigLoader',
    'Logger'
]