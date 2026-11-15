"""Candidate offline numerical policy. No native acceptance is issued here."""
import math
from .model import require


ABSOLUTE = {'K': 1e-5, 'W': 1e-6, 'J': 1e-3}


def finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def analysis_grid(mode: str, analysis: dict) -> tuple[float, ...]:
    require(isinstance(analysis, dict), 'analysis', 'analysis must be an object')
    if mode == 'steady':
        require(not analysis, 'analysis', 'steady analysis has no physical time controls')
        return ()
    require(mode == 'transient', 'mode', 'unsupported analysis mode')
    require(set(analysis) == {'startTime', 'stopTime', 'intervals', 'solver', 'tolerance'},
            'analysis', 'unexpected/missing analysis fields')
    start, stop, n, tol = (analysis[k] for k in ('startTime', 'stopTime', 'intervals', 'tolerance'))
    require(finite_number(start) and start == 0, 'analysis', 'startTime must be zero')
    require(finite_number(stop) and 1e-6 <= stop <= 1e7, 'analysis', 'stopTime outside [1e-6,1e7] seconds')
    require(type(n) is int and 1000 <= n <= 20000 and n % 2 == 0,
            'analysis', 'intervals must be even, within [1000,20000]')
    require(analysis['solver'] == 'dassl' and finite_number(tol) and tol in (1e-8, 1e-10),
            'analysis', 'unsupported solver/tolerance')
    grid = tuple(float(stop) * (i / n) for i in range(n + 1))
    time_allowance(grid)
    return grid


def time_allowance(grid: tuple[float, ...]) -> float:
    require(len(grid) >= 2 and all(finite_number(t) for t in grid), 'time_grid', 'invalid time grid')
    spacing = min(b - a for a, b in zip(grid, grid[1:]))
    require(spacing > 0, 'time_grid', 'grid not strictly increasing')
    scale = max(1.0, abs(grid[0]), abs(grid[-1]))
    epsilon = min(1e-9 * scale, spacing / 10)
    require(8 * max(math.ulp(t) for t in grid) <= epsilon,
            'time_resolution', 'insufficient floating-point separation')
    return epsilon


def match_grid(grid: tuple[float, ...], times: tuple[float, ...], *,
               maximum_shift: float | None = None) -> None:
    """One-to-one matching only, no interpolation or row repair."""
    epsilon = time_allowance(grid)
    if maximum_shift is not None:
        require(finite_number(maximum_shift) and 0 < maximum_shift <= epsilon,
                'time_sensitivity', 'invalid reference-derived matching window')
        require(8 * max(math.ulp(t) for t in grid) <= maximum_shift,
                'time_resolution', 'sensitivity window below timestamp resolution')
        epsilon = maximum_shift
    require(len(times) == len(grid), 'time_grid', 'missing or extra output samples')
    require(all(finite_number(t) for t in times), 'time_grid', 'nonfinite timestamp')
    require(all(b > a for a, b in zip(times, times[1:])), 'time_grid', 'unordered/duplicate samples')
    if maximum_shift is not None:
        require(grid[0] <= times[0] and times[-1] <= grid[-1],
                'time_sensitivity', 'sample outside reference time domain')
    require(all(abs(a - b) <= epsilon for a, b in zip(grid, times)),
            'time_sensitivity' if maximum_shift is not None else 'time_grid',
            'sample outside sensitivity-aware matching allowance' if maximum_shift is not None
            else 'sample outside matching allowance')


def local_allowance(unit: str, reference_scale: float) -> float:
    """Use ONLY this quantity's sealed independent reference scale, never native data.

    Temperature scale: max(1 K, reference excursion from its initial value),
    capped by that connected network's temperature range (also floored at 1 K).
    Differences/flows/energy changes: maximum absolute reference magnitude.
    This helper validates the supplied scale; it does not manufacture a reference.
    """
    require(unit in ABSOLUTE, 'units', 'unknown comparison unit')
    require(finite_number(reference_scale) and reference_scale >= 0, 'reference', 'invalid reference scale')
    return ABSOLUTE[unit] + 1e-6 * reference_scale


def local_balance_allowance(terms: tuple[tuple[str, float], ...]) -> float:
    """Sum error allowances ONLY for terms in one local same-unit residual."""
    require(bool(terms) and len({unit for unit, _ in terms}) == 1, 'units', 'incompatible balance terms')
    allowance = math.fsum(local_allowance(unit, scale) for unit, scale in terms)
    require(math.isfinite(allowance), 'numerical_domain', 'balance allowance overflow')
    return allowance
