# CRFB Reform Modeling Stop Sign

Before any paid reform Modal launch, or any implementation intended to enable
one, read:

1. [`REFORM_MODELING_BIBLE.md`](REFORM_MODELING_BIBLE.md)
2. [`docs/current/REFORM_MODELING_BIBLE.md`](docs/current/REFORM_MODELING_BIBLE.md)
3. [`docs/current/reform-modeling-progress.json`](docs/current/reform-modeling-progress.json)

The production artifact is a **full reform output H5 in durable storage** for
each `(year, reform, scoring_type)` cell. Aggregate CSVs, selected cached arrays,
changed-column extracts, and Modal-volume-only files are not production
substitutes.

Do not launch paid Modal work unless the progress ledger explicitly permits it.
Do not infer approval from chat history, heartbeats, old manifests, tmux logs,
or completed aggregate CSVs.

The current relaunch path requires:

- full reform H5s saved to R2, unless Max explicitly approves a named
  replacement durable target in the ledger before launch
- shared preflight-and-consume guards in both paid submitters and paid workers
- single-use approvals with transactional reservation tokens
- expected-schema validation from a pre-approved manifest
- post-H5 aggregation only, using MicroSeries/MicroDF operations

If this file conflicts with another project document, stop and resolve the
conflict in `docs/current/REFORM_MODELING_BIBLE.md` before running paid work.
