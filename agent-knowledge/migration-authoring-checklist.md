# SQLite migration author/reviewer checklist

Use this checklist for every new `src/database.py::_MIGRATIONS` entry. See
[ADR-0058](../docs/adr/0058-sqlite-migration-rollback-discipline.md).

- [ ] Append exactly one new version; never edit, reorder, or renumber history.
- [ ] Put a one-line `# rollback:` comment immediately above the entry (`_MIGRATIONS`
      entries are Python source — `#`, not the SQL `--`, or it's a syntax error).
- [ ] Use `restore backup` for rebuild, delete, or otherwise destructive work.
- [ ] Name the inverse SQL for a genuinely reversible additive change.
- [ ] Split removals across releases: soft-mark or rename `_deprecated_*` first,
      stop all reads/writes, and drop no earlier than the next release.
- [ ] Exercise upgrade from a pinned prior `PRAGMA user_version` with representative
      rows and dependent child rows.
- [ ] Confirm a pre-migration snapshot is created and passes `integrity_check`.
- [ ] Rehearse the migration against the checked-in sanitized snapshot.
- [ ] Record operator recovery as file restore when a down-step cannot preserve data.
