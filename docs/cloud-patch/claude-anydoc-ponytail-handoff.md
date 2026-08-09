# Handoff: resolve Ponytail review for anydoc branch

## Context

- Repo: `C:\Users\leone\Desktop\codeKitchen\ownix`
- Branch to fix: `origin/claude/anydoc-docs-parser-eval-jii4ro`
- Latest reviewed commit: `18d1585 feat(doc-parser): run every anydoc format like PDF across all channels`
- Review scope: Ponytail-only complexity pass. Do not broaden into correctness/security review unless a deletion changes behavior.
- User said the branch is now finished and wants all review-surfaced issues resolved.

## Suggested Skills

- `ponytail:ponytail-review` for validating that the resulting diff is shorter and no new complexity was introduced.
- `implement` for making the scoped cleanup edits.

## Findings To Resolve

1. `src/services/parse.py:L1-13`: shrink the module docstring. It repeats ADR/spike rationale. Replace with a short routing summary and leave dependency rationale in `docs/adr/0023-liteparse-document-pipeline.md` / `docs/plans/anydoc-office-parsing-spike.md`.
2. `src/services/parse.py:L132-133`: delete the unreachable `except ParseError` branch. `_parse_anydoc_sync` does not raise `ParseError`; the broad wrapper already handles parser exceptions.
3. `src/services/pdf_intake.py:L51-57`: delete the legacy `validate_pdf` API. In the finished branch it is only exercised by its own tests; `validate_document(data, name)` replaces it.
4. `tests/test_pdf_intake.py:L54-65`: delete the `validate_pdf` tests with the function.
5. `tests/test_parse_router.py:L14-43`: shrink the 30-line generated PDF helper. Reuse the existing static tiny-PDF fixture pattern from `tests/test_parse.py`, or move one tiny PDF constant into a shared test helper.
6. `web/app/(dashboard)/doc-parser/page.tsx:L63-112`: delete the `FormatHelp` tooltip/list. It duplicates support copy and even names unsupported formats; keep a compact supported-format hint in the header.
7. `docs/plans/anydoc-office-parsing-spike.md:L64-89`: delete the shipped-followup status section. The ADR amendment and diff already record what shipped; the spike doc should stay a spike artifact.

## Verification

After edits, run focused tests:

```powershell
python -m pytest tests/test_parse.py tests/test_parse_router.py tests/test_pdf_intake.py tests/test_parsed_api.py tests/test_document_ingest.py tests/test_document_processor.py -q
cd web; npm test -- --run web/app/(dashboard)/doc-parser/page.test.tsx web/components/doc-parser/doc-upload-panel.test.tsx
```

If `python` is not on PATH in this shell, use the repo's normal Python launcher/environment instead.
