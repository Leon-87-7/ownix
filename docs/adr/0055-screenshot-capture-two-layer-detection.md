# Long-video screenshot detection: ffmpeg scene-change + dedup for candidates, Gemini Vision for content selection — not OCR

The original ask wanted frames scored by "informativeness" (code, diagrams, dense visuals vs. talking heads), with OCR text-density and visual-complexity heuristics floated as candidate signals. We rejected a standalone-heuristic approach in favor of two distinct layers.

**Candidate extraction** ports `frames.py` from the open-source `bradautomates/claude-video` skill: ffmpeg scene-change detection (`select='gt(scene,0.20)'`, an 8-shot floor falling back to duration-aware uniform sampling below it) plus perceptual dedup (16×16 grayscale thumbnails, mean-pixel-diff ≤ 2.0 against the last *kept* frame — not the immediately preceding one, which is what catches slow fades). This layer only achieves "visually distinct." It cannot tell a diagram from a face — a cut between two talking-head shots survives untouched.

Content-awareness comes from a second, new layer: the deduped candidates go to a Gemini Vision call (long video has no frame/vision work today, unlike short's existing single-frame pick) that actually selects which candidates are informative and captions each one. No OCR — Gemini's judgment substitutes for a text-density heuristic entirely, and it generalizes to diagrams/UI/dense visuals that OCR alone would miss.

Considered and rejected: reusing short's flat 1fps interval sampling for long video too (wasteful at 90-minute scale, and duplicates work scene-detection already avoids); a pure heuristic pipeline (OCR text density + edge/complexity scoring) with no Gemini call (cheaper, but can't distinguish "informative" from "busy," and duplicates judgment the pipeline already pays for elsewhere).
