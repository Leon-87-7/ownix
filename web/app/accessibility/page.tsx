import type { Metadata } from 'next';
import {
  LegalArticle,
  LegalLayout,
  LegalLink,
  LegalList,
  LegalSection,
  LegalTitle,
  PublicShell,
} from '@/components/shell/public-shell';

export const metadata: Metadata = {
  title: 'Accessibility - Ownix',
};

export default function AccessibilityPage() {
  return (
    <PublicShell active="accessibility">
      <LegalLayout active="accessibility">
        <LegalArticle>
          <LegalTitle
            title="Accessibility Statement - Ownix"
            updated="Last updated: August 22, 2026"
          />

          <p>
            Ownix aims to be usable by everyone, including people who
            rely on a screen reader, keyboard-only navigation, or
            reduced-motion settings.
          </p>

          <LegalSection title="Conformance target">
            <p>
              We design and review the dashboard against{' '}
              <LegalLink href="https://www.w3.org/WAI/WCAG22/quickref/?levels=aaa">
                WCAG 2.2 Level AA
              </LegalLink>
              . That&apos;s a target we work toward, not a
              certification - Ownix is young and still changing fast,
              and some screens may not fully meet it yet.
            </p>
          </LegalSection>

          <LegalSection title="What we do">
            <LegalList>
              <li>
                Keyboard-navigable interactive elements with visible
                focus rings.
              </li>
              <li>
                A <code>prefers-reduced-motion</code> check that
                removes non-essential animation.
              </li>
              <li>
                Color is never the only signal - status and state are
                also conveyed in text or icon.
              </li>
            </LegalList>
          </LegalSection>

          <LegalSection title="Known limitations">
            <p>
              The Brain graph&apos;s force-directed map is a visual
              canvas with no non-visual equivalent of its own, so
              every node it draws is also listed in a plain,
              keyboard- and screen-reader-navigable table right below
              it - same nodes, same live topic/search filtering, real
              links you can open directly. Hit a screen that
              doesn&apos;t work with your assistive technology? Tell
              us (see Contact below) and we&apos;ll bump it up the
              list.
            </p>
          </LegalSection>

          <LegalSection title="Contact">
            <p>
              Found an accessibility barrier?{' '}
              <LegalLink href="mailto:leoneidelman09@gmail.com">
                Email Leon about accessibility
              </LegalLink>
              , with the page and what happened, and I&apos;ll follow
              up.
            </p>
          </LegalSection>
        </LegalArticle>
      </LegalLayout>
    </PublicShell>
  );
}
