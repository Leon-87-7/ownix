import type { Metadata } from 'next';
import {
  LegalArticle,
  LegalLayout,
  LegalLink,
  LegalList,
  LegalSection,
  LegalTitle,
  PublicShell,
} from '@/components/public-shell';

export const metadata: Metadata = {
  title: 'Terms of Service — vig',
};

export default function TermsPage() {
  return (
    <PublicShell active="terms">
      <LegalLayout active="terms">
        <LegalArticle>
          <LegalTitle
            title="Terms of Service — VIG (Video Intelligence Gateway)"
            updated="Last updated: July 1, 2026"
          />

          <p>
            By using the VIG Telegram bot or dashboard, you agree to
            these terms.
          </p>

          <LegalSection title="The service">
            <p>
              VIG processes video links you send it (Instagram Reels,
              YouTube Shorts, TikTok, YouTube), runs them through AI
              enrichment, and stores/returns the results to you. It is
              provided as-is, without warranty, and may change or
              become unavailable at any time.
            </p>
          </LegalSection>

          <LegalSection title="Invite-only access">
            <p>
              VIG is invite-only. After you sign in with Telegram, you
              may be asked for an email address so the operator can
              review and approve your access. Providing an email does
              not guarantee access; your account may stay pending, be
              approved, be blocked, or have access revoked later.
            </p>
            <p>
              Until your Telegram account is approved, dashboard and
              bot features may be unavailable. Use an email address
              that accurately identifies you for approval purposes.
            </p>
            <p>
              VIG is built in public, with the public. The approval
              email may also be used to contact you about improving
              VIG, gathering product feedback, and building a community
              of devs, engineers, and builders who want more clarity
              from the videos, articles, repos, and ideas they save.
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
              If you connect a Google account, VIG creates files (a{' '}
              <code>/vig</code> folder, spreadsheet, and uploads) in
              your own Drive using the <code>drive.file</code> and{' '}
              <code>spreadsheets</code> scopes. VIG only ever touches
              files it created. You can disconnect at any time by
              sending <code>/disconnect</code>.
            </p>
          </LegalSection>

          <LegalSection title="Limitation of liability">
            <p>
              VIG is a personal project, provided without warranty of
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
              🩵
            </p>
          </LegalSection>
        </LegalArticle>
      </LegalLayout>
    </PublicShell>
  );
}
