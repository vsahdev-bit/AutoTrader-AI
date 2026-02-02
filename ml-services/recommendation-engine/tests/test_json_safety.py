import json
import sys
import os

import pytest

# Match the existing test style: add src to path for imports.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import main as main


def test_json_sanitize_removes_nan_inf():
    data = {
        "a": float('nan'),
        "b": float('inf'),
        "c": -float('inf'),
        "nested": {"x": [1.0, float('nan'), 2.0]},
    }

    sanitized = main._json_sanitize(data)

    assert sanitized["a"] is None
    assert sanitized["b"] is None
    assert sanitized["c"] is None
    assert sanitized["nested"]["x"][1] is None

    # Must be JSON compliant with allow_nan=False
    json.dumps(sanitized, allow_nan=False)


def test_safe_round_defaults_on_non_finite():
    assert main._safe_round(float('nan'), 4, default=0.5) == 0.5
    assert main._safe_round(float('inf'), 4, default=0.5) == 0.5
    assert main._safe_round(-float('inf'), 4, default=0.5) == 0.5

    # When default is None, returns None for non-finite
    assert main._safe_round(float('nan'), 4, default=None) is None
