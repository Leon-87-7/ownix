# Mutation Score History

One row per week, appended automatically by the `weekly-mutation-history` job in
`.github/workflows/mutation-testing.yml` (Fridays ~3am Israel time, or a manual
`workflow_dispatch` run) — never edit rows by hand, the job owns this file.

Both scores are **full, unfiltered** runs over each tool's whole configured scope
(`cosmic-ray.toml`'s `module-path`, `stryker.config.mjs`'s `mutate` list) — no
`cr-filter-git`, no Stryker incremental cache. That makes every row comparable to
every other row, which a PR's own `backend-mutation`/`frontend-mutation` gate
result usually isn't: `cr-filter-git` narrows a PR run to only the mutants on
changed lines, so its "total" is often a small subset of the row below, not the
same scope. `rabbitloop` reads the last row here as the baseline; before flagging
a regression or improvement it checks whether the PR's own run's `total` matches
this row's — if not, the PR run was filtered/partial and isn't a fair comparison,
so it reports the PR's numbers without a verdict instead of a false regression.

| Date | Commit | Backend score | Backend killed/total | Frontend score | Frontend killed/total |
| --- | --- | --- | --- | --- | --- |
