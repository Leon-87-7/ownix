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
  title: 'Terms of Service — Ownix',
};

export default function TermsPage() {
  return (
    <PublicShell active="terms">
      <LegalLayout active="terms">
        <LegalArticle>
          <LegalTitle
            title="Terms of Service — Ownix"
            updated="Last updated: July 15, 2026"
          />

          <p>
            By using Ownix, you agree to these terms.
          </p>

          <LegalSection title="The service">
            <p>
              Ownix collects the internet you care about: videos,
              links, articles, repos, documents, and ideas. Saved
              items become part of your personal Index, organized into
              a Feed you own and can return to. Some items may also
              contribute signal to the shared Brain if you choose to
              share them.
            </p>
          </LegalSection>

          <LegalSection title="Invite-only access">
            <p>
              Ownix is invite-only while it is young. After you sign in with Telegram, you
              may be asked for an email address so your request can
              be reviewed and approved. Providing an email does
              not guarantee access; your account may stay pending, be
              approved, be blocked, or have access revoked later.
            </p>
            <p>
              Until your Telegram account is approved, dashboard and
              bot features may be unavailable. Use an email address
              that accurately identifies you for approval purposes.
            </p>
            <p>
              The approval email may also be used to contact you about
              improving Ownix, gathering product feedback, and shaping
              the product with real workflows and honest feedback.
            </p>
          </LegalSection>

          <LegalSection title="Your responsibilities">
            <LegalList>
              <li>
                Only submit content you have the right to process.
              </li>
              <li>
                Don&apos;t use the service for illegal purposes or in
                violation of the terms of the platforms the videos
                come from (Instagram, YouTube, TikTok).
              </li>
            </LegalList>
          </LegalSection>

          <LegalSection title="Google account connection">
            <p>
              If you connect a Google account, Ownix creates files (a
              folder named <code>Ownix</code>, a spreadsheet,
              and uploads) in your own Drive using the{' '}
              <code>drive.file</code> and{' '}
              <code>spreadsheets</code> scopes. Ownix only ever touches
              files it created. You can disconnect at any time by
              sending <code>/disconnect</code>.
            </p>
          </LegalSection>

          <LegalSection title="Limitation of liability">
            <p>
              Ownix is a personal project, provided without warranty of
              any kind. We are not liable for any loss or damage
              arising from its use.
            </p>
          </LegalSection>

          <LegalSection title="Changes">
            <p>
              These terms may change; continued use after a change
              means you accept the new terms.
            </p>
          </LegalSection>

          <LegalSection title="Contact">
            <p>
              Any questions? Email me here,{' '}
              <LegalLink href="mailto:leoneidelman09@gmail.com">
                leon
              </LegalLink>
            </p>
          </LegalSection>
        </LegalArticle>
      </LegalLayout>
    </PublicShell>
  );
}
