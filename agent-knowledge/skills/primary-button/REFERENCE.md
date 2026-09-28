# Reference recipe

Plain CSS that passes rules 1–3 and 5–10. Adapt it to the project's tokens rather than pasting it verbatim. Colors are placeholders: re-check contrast after swapping them.

```css
.btn-primary {
  --h: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px; /* rule 8: icon-to-label gap */
  min-height: var(--h); /* rule 1 */
  padding: 0 24px; /* rule 2 */
  border-radius: calc(var(--h) / 2); /* rule 7 */
  font-size: 17px; /* rule 3 */
  font-weight: 600;
  text-transform: none;
  color: #fff; /* rule 5: verify > 4.5:1 on the fill */
  background: linear-gradient(#2f6fed, #255bd0);
  border: 1px solid #1d4bb0; /* rule 5: edge > 3:1 on the page */
  box-shadow:
    inset 0 1px 0 rgb(255 255 255 / 0.25),
    /* rule 6: top-edge light */ 0 8px 24px rgb(0 0 0 / 0.18); /* rule 6: soft drop shadow */
  transition:
    transform 100ms ease-out,
    box-shadow 300ms ease-out,
    filter 100ms ease-out; /* rule 9 */
}
.btn-primary svg {
  width: 20px;
  height: 20px;
  flex: none;
} /* rule 8 */
.btn-primary:hover {
  filter: brightness(1.06);
}
.btn-primary:active {
  transform: translateY(1px);
  box-shadow:
    inset 0 1px 0 rgb(255 255 255 / 0.15),
    0 3px 8px rgb(0 0 0 / 0.18);
}
.btn-primary:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 3px;
}
@media (prefers-reduced-motion: reduce) {
  .btn-primary {
    transition: none;
  }
}

/* Optional recessed track (rule 6): wrap the button */
.btn-track {
  display: inline-block;
  padding: 4px;
  border-radius: 9999px;
  background: rgb(0 0 0 / 0.06);
  box-shadow: inset 0 2px 4px rgb(0 0 0 / 0.12);
}
```

## Success state (rule 10)

Three states driven by one attribute. Keep the label in the DOM so the width stays the same.

```tsx
type State = "idle" | "pending" | "done";

<button
  className="btn-primary"
  data-state={state}
  disabled={state === "pending"}
  aria-busy={state === "pending"}
>
  {state === "pending" ? <Spinner /> : state === "done" ? <CheckIcon /> : icon}
  <span>{state === "done" ? "Saved" : "Save changes"}</span>
</button>;
```

- Go back to `idle` after about 1.5s, or navigate away.
- Announce the result to screen readers with an `aria-live="polite"` region, or change the label text as above.
- On error, return to `idle` and show the error next to the button. Never show a checkmark for a failure.
