# Component Usage Inventory

**Generated:** 2026-08-15

This inventory lists all React components in `web/components/` by their usage across the web directory (app routes and component files). The count excludes the component's own test file.

## Usage Table

| Component | Area | File | Usage Count | Consuming Files |
|-----------|------|------|-------------|-----------------|
| `tooltip` | ui | `ui/tooltip.tsx` | 17 | 17 files: test/render.tsx, app/(dashboard)/layout.tsx, app/(dashboard)/jobs/[id]/page.tsx, ... |
| `page-shell` | shell | `shell/page-shell.tsx` | 11 | 11 files: app/(dashboard)/intake/page.tsx, app/(dashboard)/feed/page.tsx, app/(dashboard)/spaces/page.tsx, ... |
| `feed-states` | feed | `feed/feed-states.tsx` | 8 | 8 files: app/(dashboard)/feed/page.tsx, app/(dashboard)/spaces/page.tsx, app/(dashboard)/spaces/[id]/UrlsTab.tsx, ... |
| `job-card` | feed | `feed/job-card.tsx` | 8 | 8 files: lib/hooks/useFuseSearch.ts, lib/hooks/useFeedData.ts, lib/hooks/useInFlightPolling.ts, ... |
| `tag-picker` | ui | `ui/tag-picker.tsx` | 8 | 8 files: components/intake/intake-tag-offer.tsx, lib/hooks/useFolderTagForm.ts, components/feed/links-table.tsx, ... |
| `badges` | ui | `ui/badges.tsx` | 6 | 6 files: components/intake/intake-status-line.tsx, app/(dashboard)/spaces/[id]/UrlsTab.tsx, components/feed/job-card.tsx, ... |
| `dialog` | ui | `ui/dialog.tsx` | 6 | 6 files: app/(dashboard)/feed/page.tsx, components/feed/folder-tag-form.tsx, components/ui/export-modal.tsx, ... |
| `ghost-button` | ui | `ui/ghost-button.tsx` | 5 | 5 files: app/page.tsx, app/(dashboard)/feed/page.tsx, components/feed/submit-job.tsx, ... |
| `ownix-share-icon` | svg | `svg/ownix-share-icon.tsx` | 5 | 5 files: components/feed/job-card.tsx, components/feed/preview-card.tsx, components/feed/links-table.tsx, ... |
| `restricted-facade` | shell | `shell/restricted-facade.tsx` | 5 | 5 files: app/(dashboard)/intake/page.tsx, app/(dashboard)/prompts/page.tsx, app/(dashboard)/doc-parser/page.tsx, ... |
| `google-status` | shell | `shell/google-status.tsx` | 4 | 4 files: app/(dashboard)/layout.tsx, app/(dashboard)/feed/page.tsx, app/(dashboard)/jobs/[id]/page.tsx, ... |
| `submit-job` | feed | `feed/submit-job.tsx` | 4 | 4 files: app/(dashboard)/layout.tsx, app/(dashboard)/feed/page.tsx, components/feed/recovery-panel.tsx, ... |
| `copy-button` | ui | `ui/copy-button.tsx` | 3 | components/intake/intake-response-card.tsx, app/(dashboard)/jobs/[id]/page.tsx, components/controls/extension-tokens-panel.tsx |
| `github-icon` | svg | `svg/github-icon.tsx` | 3 | components/landing/app-slot.tsx, components/shell/sidebar.tsx, components/ui/platform-icon.tsx |
| `instagram-icon` | svg | `svg/instagram-icon.tsx` | 3 | components/landing/app-slot.tsx, components/ui/platform-icon.tsx, app/page.tsx |
| `platform-icon` | ui | `ui/platform-icon.tsx` | 3 | components/feed/job-card.tsx, components/feed/preview-card.tsx, components/feed/links-table.tsx |
| `auth-shell` | shell | `shell/auth-shell.tsx` | 2 | app/login/page.tsx, app/logout/page.tsx |
| `confirm-dialog` | ui | `ui/confirm-dialog.tsx` | 2 | app/(dashboard)/jobs/[id]/page.tsx, components/feed/links-table.tsx |
| `date-time` | ui | `ui/date-time.tsx` | 2 | components/feed/job-card.tsx, components/feed/preview-card.tsx |
| `doc-upload-panel` | doc-parser | `doc-parser/doc-upload-panel.tsx` | 2 | components/feed/submit-job.tsx, app/(dashboard)/doc-parser/page.tsx |
| `export-modal` | ui | `ui/export-modal.tsx` | 2 | app/(dashboard)/spaces/[id]/page.tsx, app/(dashboard)/doc-parser/[id]/page.tsx |
| `filter-bar` | ui | `ui/filter-bar.tsx` | 2 | app/(dashboard)/feed/page.tsx, app/(dashboard)/doc-parser/page.tsx |
| `google-drive-icon` | svg | `svg/google-drive-icon.tsx` | 2 | app/page.tsx, app/(dashboard)/jobs/[id]/page.tsx |
| `google-icon` | svg | `svg/google-icon.tsx` | 2 | app/login/page.tsx, app/(dashboard)/feed/page.tsx |
| `intake-links-list` | intake | `intake/intake-links-list.tsx` | 2 | components/intake/intake-response-card.tsx, components/doc-parser/doc-upload-panel.tsx |
| `invite-gate` | shell | `shell/invite-gate.tsx` | 2 | app/(dashboard)/layout.tsx, components/shell/sidebar.tsx |
| `job-card-tags` | feed | `feed/job-card-tags.tsx` | 2 | components/feed/job-card.tsx, components/feed/preview-card.tsx |
| `pdf-icon` | svg | `svg/pdf-icon.tsx` | 2 | components/landing/wordmark-marquee.tsx, components/landing/app-slot.tsx |
| `preview-card` | feed | `feed/preview-card.tsx` | 2 | components/intake/intake-response-card.tsx, components/feed/preview-grid.tsx |
| `preview-motif` | ui | `ui/preview-motif.tsx` | 2 | components/feed/links-table.tsx, app/page.tsx |
| `public-shell` | shell | `shell/public-shell.tsx` | 2 | app/privacy/page.tsx, app/terms/page.tsx |
| `reorder-buttons` | ui | `ui/reorder-buttons.tsx` | 2 | app/(dashboard)/spaces/[id]/UrlsTab.tsx, app/(dashboard)/spaces/[id]/ContextTab.tsx |
| `space-card` | spaces | `spaces/space-card.tsx` | 2 | lib/hooks/useSpaceList.ts, app/(dashboard)/spaces/page.tsx |
| `tag-form` | ui | `ui/tag-form.tsx` | 2 | components/intake/intake-tag-offer.tsx, app/(dashboard)/controls/page.tsx |
| `telegram-login-widget` | shell | `shell/telegram-login-widget.tsx` | 2 | app/login/page.tsx, app/page.tsx |
| `telegram-toggle` | doc-parser | `doc-parser/telegram-toggle.tsx` | 2 | app/(dashboard)/doc-parser/page.tsx, app/(dashboard)/doc-parser/[id]/page.tsx |
| `tiktok-icon` | svg | `svg/tiktok-icon.tsx` | 2 | components/landing/app-slot.tsx, components/ui/platform-icon.tsx |
| `youtube-icon` | svg | `svg/youtube-icon.tsx` | 2 | components/landing/app-slot.tsx, components/ui/platform-icon.tsx |
| `youtube-shorts-icon` | svg | `svg/youtube-shorts-icon.tsx` | 2 | components/landing/app-slot.tsx, components/ui/platform-icon.tsx |
| `app-header` | shell | `shell/app-header.tsx` | 1 | app/(dashboard)/layout.tsx |
| `app-slot` | landing | `landing/app-slot.tsx` | 1 | app/page.tsx |
| `brain-graph` | brain | `brain/brain-graph.tsx` | 1 | app/(dashboard)/brain/page.tsx |
| `chrome-icon` | svg | `svg/chrome-icon.tsx` | 1 | app/page.tsx |
| `count-up` | landing | `landing/count-up.tsx` | 1 | app/page.tsx |
| `demo-video` | landing | `landing/demo-video.tsx` | 1 | app/page.tsx |
| `desktop` | svg | `svg/desktop.tsx` | 1 | app/page.tsx |
| `dev-persona-switch` | ui | `ui/dev-persona-switch.tsx` | 1 | app/(dashboard)/layout.tsx |
| `document-source-chip` | doc-parser | `doc-parser/document-source-chip.tsx` | 1 | app/(dashboard)/doc-parser/[id]/page.tsx |
| `extension-tokens-panel` | controls | `controls/extension-tokens-panel.tsx` | 1 | app/(dashboard)/controls/page.tsx |
| `folder-tag-form` | feed | `feed/folder-tag-form.tsx` | 1 | app/(dashboard)/jobs/[id]/page.tsx |
| `footer` | ui | `ui/footer.tsx` | 1 | components/shell/auth-shell.tsx |
| `github-wordmark` | svg | `svg/github-wordmark.tsx` | 1 | components/landing/wordmark-marquee.tsx |
| `hero-gradient` | landing | `landing/hero-gradient.tsx` | 1 | app/page.tsx |
| `instagram-wordmark` | svg | `svg/instagram-wordmark.tsx` | 1 | components/landing/wordmark-marquee.tsx |
| `intake-actions` | intake | `intake/intake-actions.tsx` | 1 | components/intake/intake-response-card.tsx |
| `intake-command-palette` | intake | `intake/intake-command-palette.tsx` | 1 | components/intake/intake-composer.tsx |
| `intake-composer` | intake | `intake/intake-composer.tsx` | 1 | app/(dashboard)/intake/page.tsx |
| `intake-response-card` | intake | `intake/intake-response-card.tsx` | 1 | components/intake/intake-thread.tsx |
| `intake-state-banner` | intake | `intake/intake-state-banner.tsx` | 1 | app/(dashboard)/intake/page.tsx |
| `intake-status-line` | intake | `intake/intake-status-line.tsx` | 1 | components/intake/intake-response-card.tsx |
| `intake-tag-offer` | intake | `intake/intake-tag-offer.tsx` | 1 | components/intake/intake-response-card.tsx |
| `intake-thread` | intake | `intake/intake-thread.tsx` | 1 | app/(dashboard)/intake/page.tsx |
| `intake-upload-dropzone` | intake | `intake/intake-upload-dropzone.tsx` | 1 | app/(dashboard)/intake/page.tsx |
| `links-table` | feed | `feed/links-table.tsx` | 1 | app/(dashboard)/feed/page.tsx |
| `mobile-device-icon` | svg | `svg/mobile-device-icon.tsx` | 1 | app/page.tsx |
| `mobile-onboarding-stepper` | landing | `landing/mobile-onboarding-stepper.tsx` | 1 | app/page.tsx |
| `mock-provider` | shell | `shell/mock-provider.tsx` | 1 | app/layout.tsx |
| `no-preview-ring` | ui | `ui/no-preview-ring.tsx` | 1 | components/feed/preview-card.tsx |
| `onboarding-stepper` | landing | `landing/onboarding-stepper.tsx` | 1 | app/page.tsx |
| `openai-icon` | svg | `svg/openai-icon.tsx` | 1 | app/page.tsx |
| `ownix-add-icon` | svg | `svg/ownix-add-icon.tsx` | 1 | app/(dashboard)/feed/page.tsx |
| `preview-grid` | feed | `feed/preview-grid.tsx` | 1 | app/(dashboard)/feed/page.tsx |
| `puzzle-piece` | svg | `svg/puzzle-piece.tsx` | 1 | app/page.tsx |
| `recovery-panel` | feed | `feed/recovery-panel.tsx` | 1 | app/(dashboard)/feed/page.tsx |
| `scroll-to-top` | shell | `shell/scroll-to-top.tsx` | 1 | app/(dashboard)/layout.tsx |
| `sheet` | ui | `ui/sheet.tsx` | 1 | components/feed/submit-job.tsx |
| `sidebar` | shell | `shell/sidebar.tsx` | 1 | app/(dashboard)/layout.tsx |
| `stat-card` | feed | `feed/stat-card.tsx` | 1 | components/feed/stats-overview.tsx |
| `stats-overview` | feed | `feed/stats-overview.tsx` | 1 | app/(dashboard)/feed/page.tsx |
| `submit-url-form` | feed | `feed/submit-url-form.tsx` | 1 | components/feed/submit-job.tsx |
| `sw-register` | shell | `shell/sw-register.tsx` | 1 | app/layout.tsx |
| `tab-bar` | ui | `ui/tab-bar.tsx` | 1 | app/(dashboard)/spaces/[id]/page.tsx |
| `telegram-icon` | svg | `svg/telegram-icon.tsx` | 1 | app/page.tsx |
| `tiktok-wordmark` | svg | `svg/tiktok-wordmark.tsx` | 1 | components/landing/wordmark-marquee.tsx |
| `wordmark-marquee` | landing | `landing/wordmark-marquee.tsx` | 1 | app/page.tsx |
| `youtube-wordmark` | svg | `svg/youtube-wordmark.tsx` | 1 | components/landing/wordmark-marquee.tsx |

## Zero Real Usages

The following 3 components are imported by nothing but their own test file (if at all) — these are deletion candidates:

| Component | Area | File |
|-----------|------|------|
| `markdown-editor` | ui | `ui/markdown-editor.tsx` |
| `onboarding-textblock` | landing | `landing/onboarding-textblock.tsx` |
| `public-header` | ui | `ui/public-header.tsx` |

