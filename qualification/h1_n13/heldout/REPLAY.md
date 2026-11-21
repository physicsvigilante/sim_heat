# Replay the first TwinBridge attempt

Frozen solver f05f6a8fbdfd5ac177a5441d22b40dda6bf8e0d4, original case/oracle commit 892e9e47e138b5ffd040e952d1ffa6598d2a052d. Run from the SIM_HEAT repository root with the CI Python environment, without Python optimization flags. This offline sequence does not invoke OpenModelica.

```sh
python -B -m qualification.h1_n13.conduction --study qualification/h1_n13/heldout/study.json --root qualification/h1_n13/heldout --facts qualification/h1_n13/heldout/facts.json --facts-sha256 57c393f2b11bf658a378b6fa6ab96425b14116b8c2fc519e4bedba1e883d1783
python -B qualification/h1_n13/heldout/oracle.py qualification/h1_n13/heldout/first-output.json.gz
python -B -m qualification.h1_n13.heldout.controls
```

The first command exited 0. Its stdout survives byte-for-byte in first-output.json.gz. The uncompressed stdout SHA-256 is 54cf4f39481d8b882827a6aaba7480c5865b74c4b64c80a3662bbd5c78ca787b. Windows wrote CRLF after the JSON object. Compare decoded JSON on other platforms. First stderr is empty. The pinned local interpreter SHA-256 is 5341746f92483a93e44c313de830f2fba2956f0759094404a16b2fed06c9a2ed. The following two commands reproduced oracle-results.json and control-results.json respectively (compare decoded JSON objects).

The independent examiner selected TwinBridge after the solver freeze. All mathematical assumptions, data, signed equations and comparison code were recorded before the first execution. Reference data and the authored model were entered separately by the same case selector. The oracle uses only the Python standard library and exercise equations. Four controls exercise candidate admission and three exercise reviewer evidence checking. The originals and their hashes are unaffected by each mutation.
