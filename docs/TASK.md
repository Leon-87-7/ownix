# Task: Mobile responsiveness fixes

## 1. Segmented tabs line breaks on mobile

The new content-type segmented control (`web/components/feed/filter-bar.tsx`,
`SegmentedTabs`) overflows awkwardly on small screens,making a horizontal scroll.

**Wanted:** on small screens, render the tabs as separate tab buttons (stacked
or wrapped individual buttons) instead of one continuous segmented line.
with out the motion on hover. (just as it was pre-`SegmentedTabs`).

## 2. Tag creation modal not responsive

The create-tag modal (`web/components/TagPicker.tsx`, `CreateTagModal`) and the `TagForm`, `web\app\(dashboard)\controls\page.tsx` don't adapt to small screens — the Name/Meaning row and the 9-column color grid don't
fit well on narrow viewports.

**Wanted:** make the create-tag form responsive (stack fields, reflow the color
grid) for small screens.
