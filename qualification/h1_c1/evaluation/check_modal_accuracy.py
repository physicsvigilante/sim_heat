"""Same-evaluator C1 task-only two-state analytic cross-check.

CHECKING EVIDENCE ONLY. Do not import production h1 modules or read native
output. This script is NOT a new engine physical law, independent expert
reference certification, or a simulated OpenModelica MAT/CSV.
Physical inputs are separately transcribed from the original Stage 1 task.
"""
import hashlib
import json
import math
from pathlib import Path

import mpmath as mp
import numpy as np
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "h1/cases/H1_C1_MODAL/study.json"
MODEL = ROOT / "h1/cases/H1_C1_MODAL/model.mo"
PLAN = ROOT / "qualification/h1_c1/evaluation/C1_FIRST_MODAL_PLAN_CHECKING_ONLY.json"

def run():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    study = json.loads(STUDY.read_text(encoding="utf-8"))
    assert hashlib.sha256(MODEL.read_bytes()).hexdigest() == plan["firstModelSha256"]
    assert hashlib.sha256(STUDY.read_bytes()).hexdigest() == plan["evaluatorProspectiveStudySha256"]
    assert study["analysis"] == plan["evaluatorAnalysis"]
    mp.mp.dps = 95
    q = mp.mpf
    cl = q("0.25") * q("500")
    cr = q("0.30") * q("600")
    gh = q("150") * q("0.00030") / q("0.10")
    gf = q("200") * q("0.00050") / q("0.10")
    gr = q("50") * (mp.pi * (q("0.020")/2)**2) / q("0.050")
    gc = q("100") * q("0.00040") / q("0.10")
    gb = gf + gr
    A = mp.matrix([[-(gh+gb)/cl, gb/cl], [gb/cr, -(gb+gc)/cr]])
    B = mp.matrix([gh*q("363.15")/cl, gc*q("283.15")/cr])
    initial = mp.matrix([q("293.15"),q("333.15")])
    steady = -mp.inverse(A) * B
    a,d = A[0,0],A[1,1]
    discriminant = mp.sqrt((a-d)**2+4*A[0,1]*A[1,0])
    slow = -(a+d+discriminant)/2
    fast = -(a+d-discriminant)/2
    assert 0 < slow < fast
    horizon = 5/slow
    stop = float(study["analysis"]["stopTime"])
    n = study["analysis"]["intervals"]
    assert n % 2 == 0 and 1000 <= n <= 10000
    assert abs(stop-float(horizon)) < 1e-9
    step_mode = (q(str(stop))/n)*fast
    assert step_mode <= q("0.01")
    # Two separate numerical formulations of the same externally fixed task
    # equations: 95-digit analytic spectral projectors vs float64 expm.
    I = mp.eye(2)
    Af = np.array([[float(A[i,j]) for j in range(2)] for i in range(2)])
    Bf = np.array([float(B[i]) for i in range(2)])
    ssf = -np.linalg.solve(Af,Bf)
    initialf = np.array([293.15,333.15])
    max_error=0.0; at_time=0.0; samples={}
    for k in range(n+1):
        t=stop*(k/n)
        high_t=q(t)  # exact binary float converted to arbitrary precision
        expA=(mp.exp(-slow*high_t)*(A+fast*I)/(fast-slow)
              +mp.exp(-fast*high_t)*(A+slow*I)/(slow-fast))
        high=steady + expA*(initial-steady)
        cross=ssf+expm(Af*t)@(initialf-ssf)
        err=max(abs(float(high[j])-float(cross[j])) for j in range(2))
        if err>max_error:
            max_error=err;at_time=t
        if k in (0,125,160,n):
            gap=float(high[0]-high[1])
            samples[str(k)]={
                "timeSeconds":t,"leftBufferK":float(high[0]),
                "rightBufferK":float(high[1]),
                "leftMinusRightK":gap,
                "flatBridgeOrientedW":float(gf*(high[0]-high[1])),
                "roundBridgeOrientedW":float(gr*(high[0]-high[1])),
                "meaning":"checking-only predicted result, NOT native observed data",
            }
    assert max_error < 1e-9, ("checking methods diverge",max_error)
    assert samples["125"]["leftMinusRightK"] < 0 < samples["160"]["leftMinusRightK"]
    data={
      "schema":"sim_heat.c1_evaluator_accuracy_corrob/1",
      "status":"same_evaluator_two_algorithm_check_not_independent_certification",
      "taskSourceSha256":plan["sourceTaskSha256"],
      "firstModelSha256":plan["firstModelSha256"],
      "originalFirstStudySha256":plan["firstStudySha256"],
      "prospectiveStudySha256":plan["evaluatorProspectiveStudySha256"],
      "gridPointsChecked":n+1,"timeStepFastRateProduct":float(step_mode),
      "positiveModalRatesPerS":{"slow":float(slow),"fast":float(fast)},
      "fiveSlowTimeConstantsSeconds":float(horizon),
      "maximumTemperatureMethodDisagreementK":max_error,
      "worstTimeSeconds":at_time,
      "asymptoticBodyTemperaturesK":[float(steady[0]),float(steady[1])],
      "selectedSavedGridIndices":samples,
      "limitations":[
        "Original Stage 2 author first study remains unchanged.",
        "Two algorithms implemented by same evaluator do not certify an independent physical reference error bound.",
        "All trajectories here are checking-only analytical predictions, not an OpenModelica run.",
        "Prospective native grid and reference still require independent R2 assessment and an explicit bounded native run plan.",
      ],
    }
    return data

if __name__=="__main__":
    print(json.dumps(run(),indent=2,sort_keys=True,allow_nan=False))
