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
  title: 'Privacy Policy — Ownix',
};

export default function PrivacyPage() {
  return (
    <PublicShell active="privacy">
      <LegalLayout active="privacy">
        <LegalArticle>
          <LegalTitle
            title="Privacy Policy — Ownix"
            updated="Last updated: July 1, 2026"
          />

          <p>
            Ownix is a quiet tool for collecting the internet you care
            about. Saved videos, links, articles, repos, documents, and
            ideas become part of your personal Index and may contribute
            signal to the shared Brain if you choose to share them.
          </p>

          <LegalSection title="What we collect">
            <LegalList>
              <li>
                Your Telegram identity (chat ID, name, username) —
                used to identify your account and route your data.
              </li>
              <li>
                The email address you provide for invite approval,
                plus your access status (<code>pending</code>,{' '}
                <code>approved</code>, or <code>blocked</code>).
              </li>
              <li>
                Links and documents you save, plus generated analysis
                such as transcripts, descriptions, tags, and summaries.
              </li>
              <li>
                If you connect your Google account: an OAuth token
                scoped to Google Drive (<code>drive.file</code>) and
                Google Sheets (<code>spreadsheets</code>). This lets
                Ownix create a folder currently named <code>/vig</code>{' '}
                and a spreadsheet in your Drive and write your results
                there. Ownix can only see or edit files it creates
                itself — it cannot access any other file already in
                your Drive.
              </li>
            </LegalList>
          </LegalSection>

          <LegalSection title="How we use approval email">
            <p>
              Ownix is invite-only while it is young. We use the approval email to review
              access requests, associate the request with your
              Telegram account, and contact you about access if
              needed.
            </p>
            <p>
              <span className="border-b border-dashed border-muted pb-0.5 font-medium text-body">
                Ownix is shaped with the people using it.
              </span>{' '}
              We may use this email to ask for feedback, discuss
              feature improvements, share relevant Ownix updates, and
              understand how people collect, return to, and share the
              internet they care about.
            </p>
            <p>
              We do not sell your email or share it with third
              parties.
            </p>
          </LegalSection>

          <LegalSection title="What we don't collect">
            <LegalList>
              <li>
                We never request access to your Gmail, your existing
                Drive files, or any Google data beyond the scopes
                listed above.
              </li>
              <li>
                We don&apos;t sell or share your data with third
                parties.
              </li>
            </LegalList>
          </LegalSection>

          <LegalSection title="How your data is stored">
            <p>
              Video analysis results are stored in a private database
              and cloud storage bucket, scoped to your Telegram
              account. Your Google OAuth token, if you connect one, is
              stored encrypted and used only to write your own results
              to your own Drive/Sheets.
            </p>
          </LegalSection>



          <LegalSection title="Functional preview cookies">
            <p>
              Ownix may set a session cookie named <code>ownix_preview</code> to keep the read-only preview active while you browse. It does not identify you or track you across sites.
            </p>
          </LegalSection>

          <LegalSection title="Revoking access">
            <p>
              Send <code>/disconnect</code> to the bot at any time to
              revoke your Google connection — this deletes your stored
              token and revokes it with Google. You can also revoke
              access directly from your{' '}
              <LegalLink href="https://myaccount.google.com/permissions">
                Google Account&apos;s third-party access settings
              </LegalLink>
              .
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
