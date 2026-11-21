# When does an authored observation cross a threshold?

Choose a request ID already declared by a transient study and give the threshold in that request's SI unit (K, W or J). The observer follows the requested operands and their orientation, including signed temperature differences and changes in a body's stored energy.

For two isolated bodies initially 60 K apart, D2 declares the hot-minus-cold temperature difference as `difference`. The temperature gap drops through 1 K between 7668.75 and 7678.125 s. The analytical time is 1875 ln(60) s. From the repository root:

```sh
python -B -m tools.observation_passages --root h1/cases/D2 --study h1/cases/D2/study.json --facts h1/reference_cases/D2.json --facts-sha256 befcb977a08bdb4d3f15d903ebafccf910d83675f8d1a92f1988bca74a8a547a --request-id difference --threshold 1 --unit K
```

In D1 a 500 J/K body gains up to 30 kJ as it warms toward the reservoir. Select `energy` at 15000 J to investigate when it has gained half this amount. The time is 2500 ln(2) s. The same command accepts temperature and signed heat-rate requests.

Each reported passage requires two samples whose bounded values lie strictly on opposite sides. Samples whose uncertainty reaches the threshold can widen a bracket. Several passages may occur between samples, and no observed passage leaves that possibility open. The output identifies the study, model, checking facts, request, threshold and unit.
