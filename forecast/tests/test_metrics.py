import numpy as np
import pandas as pd

import metrics


def test_pinball_matches_hand_cases():
    y = np.array([1.0, 1.0])
    assert metrics.pinball(y, np.array([0.5, 1.5]), 0.5) == 0.25            # mean of 0.25, 0.25
    assert np.isclose(metrics.pinball(y, np.array([0.5, 1.5]), 0.1), (0.1 * 0.5 + 0.9 * 0.5) / 2)
    assert metrics.pinball(y, y, 0.9) == 0.0


def test_coverage_below():
    assert metrics.coverage_below(np.array([1.0, 2.0, 3.0, 4.0]), np.array([1.5, 1.5, 1.5, 5.0])) == 0.5


def test_sort_quantiles_fixes_crossing():
    f = pd.DataFrame({"q10": [0.9, 0.1], "q50": [0.5, 0.5], "q90": [0.1, 0.9]})
    s = metrics.sort_quantiles(f)
    assert list(s["q10"]) == [0.1, 0.1] and list(s["q90"]) == [0.9, 0.9]
    assert list(f["q10"]) == [0.9, 0.1]  # input untouched
