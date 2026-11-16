"""Checking-only, independently written energy-balance ODE for TEACH_RING4.

This test is not imported by the physical library, runner, viewer or native
result writer. Constants are re-entered from the pre-fixed TASK.md, not parsed
from model.mo. It compares an independent DOP853 initial-value solver against
the predeclared H1 reference trajectory at exactly saved sample times.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from h1 import reference

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT/'h1/reference_cases/TEACH_RING4.json'
CAPACITY = np.array([500.0, 900.0, 720.0, 1100.0])
INITIAL = np.array([303.15, 323.15, 288.15, 313.15])
BATH_T = 353.15
# Signed orientation (a,b,G): -1 denotes the boundary node.
LINKS = [(-1,0,0.30),(0,1,0.16),(1,2,0.20),
         (2,3,0.20),(3,0,0.14),(0,2,0.24)]

def dTdt(_time, temperatures):
    power = np.zeros(4)
    for a,b,G in LINKS:
        origin = BATH_T if a == -1 else temperatures[a]
        flow = G*(origin - temperatures[b])
        if a >= 0:
            power[a] -= flow
        power[b] += flow
    return power/CAPACITY

def check():
    points = np.array([0.,300.,1200.,3600.,9000.,18000.,24000.])
    numerical = solve_ivp(dTdt,(0.,24000.),INITIAL,method='DOP853',
                          rtol=1e-12,atol=1e-12,dense_output=True)
    if not numerical.success:
        raise RuntimeError(numerical.message)
    result = numerical.sol(points).T
    bundle = reference.prepare(reference.read_reference(REF))
    indices = (points/12).astype(int)
    reference_values = np.stack(
        [np.asarray(bundle['columns'][name+'.T'])[indices] for name in 'ABCD'],
        axis=1)
    worst = float(np.max(np.abs(result-reference_values)))
    print('Checking-only independent DOP853 versus H1 reference:')
    print('maximum selected-temperature difference K =', worst)
    for t,row in zip(points,result):
        print('t=',t,'temperatures_K=',[float(x) for x in row])
    assert worst < 1e-7
    assert np.allclose(dTdt(0.,INITIAL),
                       np.array([16.0,-10.2,15.6,-6.4])/CAPACITY,
                       rtol=0,atol=1e-13)
    # These data are a checking reference, not replacement native output.
    return worst

if __name__ == '__main__':
    check()
