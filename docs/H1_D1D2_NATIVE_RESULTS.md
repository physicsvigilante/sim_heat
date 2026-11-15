# H1 D1/D2 primary transient cloud results

Date: 2026-11-15. This records an actual successful cloud workflow, not a post-hoc correction of a failed run. Status: **primary transient diagnostics passed; full H1 native qualification not claimed**.

## Exact execution and retained evidence

- Run: https://github.com/physicsvigilante/sim_heat/actions/runs/43691263273
- Executed commit: `1b68b14dd05c5eb8f148b02055890563cdc32095`.
- Branch: `experiment/h1-cloud-transients-once`; draft PR #7.
- Artifact: `14152886226`, `h1-d1d2-transient-evidence`, 842289 bytes.
- ZIP SHA-256: `8fc38b9e2f040b48ab5cbeab34e8698b7c99c4d462a1e31e8bc33b0395185379`.
- All **168 file hashes** in the artifact manifest match the downloaded bytes.
- Executed budget: **2 builds, 2 model launches, 1 explicit compiler version query**; no retries. Setup-action package probes remain in the installation logs.
- Runtime: OpenModelica 1.27.0, MSL 4.0.0, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0 on GitHub-hosted Ubuntu 24.04. Actual platform string: Linux-7.0.0-1014-aws-x86_64-with-glibc2.39. Compiler binary and installed MSL .mo source hashes are retained in the artifact.
- Cloud offline preflight: **130 tests passed**, zero failures/errors. Both references were sealed before native compilation. Actual initialization XML settings matched each authored study before launch.

## Observed results

| Case | Horizon | Canonical samples | Required outputs | Passing checks | Largest error/allowance ratio |
|---|---:|---:|---:|---:|---:|
| D1, finite body and reservoir | 12500 s | 1001 | 12/12 | 28/28 | 0.4765970406412102 |
| D2, two isolated bodies | 9375 s | 1001 | 14/14 | 34/34 | 0.44281392901027733 |

Both retain DASSL tolerance 1e-8 and 1000 intervals. A ratio at or below 1 passes the existing criterion; no allowance, physical parameter or output grid was changed after seeing results.

D1 native initial values: body 293.15 K, heat input +12 W, energy change 0 J. At 12500 s: body 352.74571956572044 K, heat input 0.080856086855908421 W, energy gain 29797.859782860229 J. Maximum absolute temperature discrepancy from the presealed reference over all checked samples: 1.5593939338032214e-5 K. Maximum absolute energy discrepancy: 0.00779696966856136 J. The body and whole-network flow-integral checks pass with their unchanged quadrature-aware allowances.

D2 native initial values: hotter body 353.15 K and heat input -12 W; cooler body 293.15 K and heat input +12 W; oriented rod flow +12 W. At 9375 s: body temperatures 308.45321583344645 K and 308.04892805551776 K; rod flow 0.080857555585737373 W. Maximum absolute temperature discrepancy: 2.0677990107742517e-5 K. The largest absolute sum of the two recorded stored-energy changes is 2.837623469531536e-10 J. The last temperatures are finite-time samples, not exact arrival at the 308.15 K analytical asymptotic equilibrium.

Both cases pass initial-state, reference-history, rod-law/orientation, junction temperature/flow, body-energy ownership and integrated-exchange checks. D2 additionally demonstrates isolated-network energy conservation. Alias channels retain recorded provenance; separate names are not claimed to be independent measurements.

## Reuse and preservation

The shared Modelica library, both authored model/study files, reference specifications, numerical policies, corrected MAT reader and generic verifier retain their previous bytes. Only a study-driven runner, its tests, a pinned plan, workflow and documentation were added. The runner reads model identity/settings/export registry rather than selecting physics by case or illustration name. D1 and D2 took the same compiled-library, execution, decoding and checking path.

The downloaded MAT files were decoded and checked once more offline using the same pinned implementation. For both cases, normalized CSV bytes and every verifier report field match the cloud outputs exactly. No downloaded executable was run and no native job was repeated. The original cloud evidence remains unchanged.

## Limits and next stage

This is evidence for two development-exposed transient arrangements, not a frozen unfamiliar-author transfer claim. The current checker deliberately labels observations diagnostic_only and nativeQualified=false; actual build/launch evidence is supplied separately by the execution manifest and logs. Formal reference-accuracy/independent-acceptance obligations are not silently closed.

Tighter-tolerance and denser-grid companions, native conductivity revision, other edge cases, C1 and classroom effectiveness remain untested natively by this batch. No C1 was selected. No prior failed attempt was overwritten, no production physics was specialized, no merge was needed, and main was not changed. The next useful investigation is the existing conductivity-change scenario plus the planned numerical-resolution checks through this same runner.
