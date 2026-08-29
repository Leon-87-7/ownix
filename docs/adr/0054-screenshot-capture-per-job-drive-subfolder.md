# Long-video screenshot capture uses a per-job Drive subfolder, not the flat shared-folder pattern

Every existing Drive artifact in this codebase — short's `{job_id}_short.md`, long's `{slug}.md`, PRD docs, exports — lands in one flat, pipeline-level folder (`GOOGLE_DRIVE_FOLDER_SHORT`/`_LONG`/`_PRD`/etc.). `upload_file()` always targets a fixed folder id, and `drive.py` has no folder-creation capability at all.

Screenshot capture (see [[Screenshot capture]] in CONTEXT.md) needs a real per-video subfolder instead: the feature's entire output requirement is a single "link out to this video's screenshots" on the job detail page, and a flat folder with job-id-prefixed filenames can't produce that — Drive has no stable "folder view scoped to one prefix" URL. We're adding one new `drive.py` capability (`files().create()` with `mimeType: application/vnd.google-apps.folder`) under a new `GOOGLE_DRIVE_FOLDER_SCREENSHOTS` root, one subfolder per job named `{job_id}_{slug}`.

This is deliberately the first departure from the flat-folder convention in this codebase. Don't assume it should be copied elsewhere without the same "needs a browsable per-item container" justification — for most Drive artifacts here, the flat pattern is still correct.
