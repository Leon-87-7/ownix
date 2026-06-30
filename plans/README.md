# Improvement plans

Advisor-written plans for execution by a separate agent. Each plan is self-contained.

Written against commit `92ad1c5`.

## Index

| #   | Plan                                                          | Category   | Effort | Risk | Status |
| --- | ------------------------------------------------------------ | ---------- | ------ | ---- | ------ |
| 001 | [Fix mobile horizontal overflow on Controls/Prompts](001-mobile-overflow-fix.md) | Bug / responsive | S | Low | DONE |
| 002 | [Mobile: sidebar sliver → full drawer + edge pull-tab](002-mobile-sidebar-drawer.md) | Responsive / UX | S | Low | DONE |

## Execution order

Both are independent (different files) and can land in either order or together.
001 is the safer, smaller change; 002 restructures the dashboard shell. Doing
both gives the full "simpler on small screens" result the user asked for.

## Considered and rejected

- _none yet_
