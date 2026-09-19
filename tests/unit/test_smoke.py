"""Smoke tests for basic functionality."""

import sys


def test_python_version():
    """Test Python version is 3.11+."""
    assert sys.version_info >= (3, 11)
