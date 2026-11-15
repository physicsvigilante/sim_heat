"""Read-only common-time diagnostics; never computes production trajectories.

Inputs must already have passed the unchanged native-candidate checker. Use
primary presealed allowances, not a fitted tolerance or their pairwise sum.
"""
import numpy as np
from h1.model import require
from h1.reference import trapezoids


def compare(primary, primary_reference, companion, companion_reference):
    a,b=primary_reference,companion_reference
    sa,sb=a['spec'],b['spec']
    for key in ('mode','modelSha256','nodes','bodies','boundaries','rods'):
        require(sa[key]==sb[key], 'comparison', 'physical model changed: '+key)
    require(sa['analysis']['startTime']==sb['analysis']['startTime'] and
            sa['analysis']['stopTime']==sb['analysis']['stopTime'] and
            sa['analysis']['solver']==sb['analysis']['solver'], 'comparison', 'horizon/solver changed')
    require(set(a['columns'])==set(b['columns']) and a['units']==b['units'],
            'comparison', 'output meanings changed')
    ta,tb=np.asarray(a['grid']),np.asarray(b['grid'])
    locations={float(t):i for i,t in enumerate(tb)}
    require(len(locations)==len(tb) and all(float(t) in locations for t in ta),
            'comparison', 'no exact common grid; interpolation refused')
    indices=np.array([locations[float(t)] for t in ta])
    checks=[]
    for key in a['columns']:
        x,y=np.asarray(primary[key]),np.asarray(companion[key])
        require(x.shape==ta.shape and y.shape==tb.shape and np.isfinite(x).all()
                and np.isfinite(y).all(), 'comparison', 'invalid candidate samples')
        epsilon=a['allowances'][key]
        require(epsilon==b['allowances'][key] and np.isfinite(epsilon) and epsilon>0,
                'comparison', 'independent comparison allowance differs')
        delta=np.abs(x-y[indices]);worst=int(np.argmax(delta))
        checks.append({'quantity':key,'unit':a['units'][key], 'maximumDifference':float(delta[worst]),
                       'allowance':epsilon,'maximumRatio':float(delta[worst]/epsilon),
                       'worstTime':float(ta[worst]),'passed':bool((delta<=epsilon).all())})
    quadrature=[]
    for key in a['flowIntegrals']:
        # These diagnostics distinguish sampled-flow quadrature from state
        # accuracy. No new allowance or monotonic-convergence assertion is made.
        p=trapezoids(ta,np.asarray(primary[key]))-np.asarray(a['flowIntegrals'][key])
        c=trapezoids(tb,np.asarray(companion[key]))-np.asarray(b['flowIntegrals'][key])
        rp=trapezoids(ta,np.asarray(a['columns'][key]))-np.asarray(a['flowIntegrals'][key])
        rc=trapezoids(tb,np.asarray(b['columns'][key]))-np.asarray(b['flowIntegrals'][key])
        quadrature.append({'flow':key,'primaryMaximumIntegralErrorJ':float(np.max(np.abs(p))),
          'companionMaximumIntegralErrorJ':float(np.max(np.abs(c))),
          'primaryReferenceGridErrorJ':float(np.max(np.abs(rp))),
          'companionReferenceGridErrorJ':float(np.max(np.abs(rc)))})
    return {'stage':'common_time_comparison','status':'checks_passed' if all(c['passed'] for c in checks) else 'checks_failed',
      'nativeQualified':False,'commonSamples':len(ta),'primarySeal':a['seal'],'companionSeal':b['seal'],
      'policy':'unchanged primary per-output allowance; no interpolation or sum-of-allowances',
      'checks':checks,'quadratureDiagnostics':quadrature}
