## Merge Policy

Never merge into `main` (or `master`) unless the user explicitly names `main` as the target in that message — e.g. "merge to main", "land on main", "push to main".

"Merge the PR" is **not** sufficient. Before merging any PR, check its base branch. If the base branch is `main`, stop and ask for confirmation before proceeding. If the base branch is `dev` or any other non-main branch, proceed normally.
