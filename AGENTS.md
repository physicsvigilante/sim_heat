# SIM_HEAT contribution and review boundaries

Source of truth for shared two-ChatGPT coordination: [review_sandbox/PROTOCOL.md](https://github.com/physicsvigilante/review_sandbox/blob/main/PROTOCOL.md) and [REVIEW-RISK-POLICY.md](https://github.com/physicsvigilante/review_sandbox/blob/main/REVIEW-RISK-POLICY.md). The central repository stores **review requests, prompts, and reviewer findings only**. This project repository owns Modelica, Python, tests, CI, original inputs, and native evidence.

Read [docs/H1_IMPLEMENTATION_CONTRACT.md](docs/H1_IMPLEMENTATION_CONTRACT.md), [docs/H1_OFFLINE_AMENDMENT.md](docs/H1_OFFLINE_AMENDMENT.md), and [qualification/h1_c1/FREEZE.md](qualification/h1_c1/FREEZE.md) before changing physics, authoring grammar, numerical/error limits, observation semantics, or native provenance. Earlier reports and failed attempts are immutable historical records, not automatically current acceptance.

**Risk classification:** docs/process R0; bounded non-semantic UI or glue R1; physics, numerical methods, runtime controller, result semantics, provenance or qualification R2. First integration of H1 into `main` is R2. R2 demands pinned CI, negative/refusal controls, real native and independent reference evidence relevant to the changed scope, and one independent-in-context Chat B review. A green test suite does not lower risk by itself.

## Local Codex workflow

The owner authorizes Chat A to choose successive JEE-relevant milestones, implement them locally, test, push and publish draft PRs until the owner asks to stop. Prefer investigations that compose existing thermal components. Run physics offline and keep source PRs unmerged. Milestone selection, pushes and reviewer dispatch may proceed under this standing instruction.

For R2 work, Chat A freezes the implementation, runs local checks, opens a draft PR and verifies CI on its exact head. Record the base and head SHAs, acceptance scope, CI jobs and artifact identities in the central review packet. Publish the request, reviewer prompt and status under the source PR number.

In SIM_HEAT the owner selected a fresh Codex reviewer subagent for the Chat B role. Start the reviewer with a separate context and supply the pinned packet. The reviewer independently checks the source and evidence, identifies its role, and publishes its own new report under the packet's reviews directory. Chat A can dispatch the published prompt directly. The hub retains the requests and reports.

When the reviewer publishes, Chat A fetches the exact report, records its verdict and reproduces findings. Fix confirmed defects with regression evidence, exact-head CI and targeted independent review as needed. Preserve earlier evidence and reports. **Merge only with explicit owner approval**, then verify post-merge CI and update the hub record.

**Execution and preservation:** no automatic OpenModelica native jobs from standard CI. Never trust source/model parameters, values, missing outputs, aliases, or statuses just because validation succeeded. Use the generic admitted grammar, reference preparation, source pins and signed-flow/energy checks. No arrangement-specific solver fallback, reference-filled native fields, or fabricated independent evidence. Existing `diagnostic_only`/`nativeQualified=false` meanings are not silently promoted.

Historical one-shot cloud-runner files and workflows live on unmerged experiment branches; do not restore or enable those production triggers merely for convenience. The C1 external-author experiment remains a separately selected, independently recorded claim.