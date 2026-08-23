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
  title: 'Privacy Policy - Ownix',
};

export default function PrivacyPage() {
  return (
    <PublicShell active="privacy">
      <LegalLayout active="privacy">
        <LegalArticle>
          <LegalTitle
            title="Privacy Policy - Ownix"
            updated="Last updated: August 22, 2026"
          />

          <p>
            Ownix is a quiet tool for collecting the internet you care
            about. Saved videos, links, articles, repos, documents,
            and ideas become part of your personal Index and may
            contribute signal to the shared Brain if you choose to
            share them.
          </p>

          <LegalSection title="What we collect">
            <LegalList>
              <li>
                Your Telegram identity (chat ID, name, username, and
                profile photo URL) - used to identify your account and
                route your data.
              </li>
              <li>
                The email address you provide for invite approval,
                plus your access status (<code>pending</code>,{' '}
                <code>approved</code>, or <code>blocked</code>).
              </li>
              <li>
                Links and documents you save, the analysis Ownix
                generates from them (transcripts, descriptions, tags,
                summaries), and your job history - what you submitted
                and when. Kept until you delete the job or link
                yourself; see &quot;Deleting your data&quot; below.
              </li>
              <li>
                If you choose to keep a saved item in the shared
                Brain, Ownix generates a numeric embedding (a
                similarity fingerprint, not human-readable text) from
                its content to power search and the link graph.
              </li>
              <li>
                If you connect your Google account: an OAuth token
                scoped to Google Drive (<code>drive.file</code>) and
                Google Sheets (<code>spreadsheets</code>). This lets
                Ownix create a folder named <code>Ownix</code> and a
                spreadsheet in your Drive and write your results
                there. <code>drive.file</code> only lets Ownix see or
                edit files it creates itself, or files you explicitly
                open or share with Ownix - it cannot access any other
                file already in your Drive. Ownix currently only
                creates files; it doesn&apos;t use file-picker or
                &quot;open with&quot; flows to access files you didn&apos;t
                create with it.
              </li>
            </LegalList>
          </LegalSection>

          <LegalSection title="How AI processes your content">
            <p>
              Google&apos;s Gemini models do the actual work:
              transcribing video, describing images, pulling text off
              photos (OCR), and writing the summaries, tags, and
              embeddings you see in your Feed and the Brain. Whatever
              you submit - a URL, a file, a transcript - gets sent to
              Gemini to make that happen.
            </p>
          </LegalSection>

          <LegalSection title="How we use approval email">
            <p>
              Ownix is invite-only while it is young. We use the
              approval email to review access requests, associate the
              request with your Telegram account, and contact you
              about access if needed.
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
                We never sell your data. We do send it to the
                providers below, but only to get your job done - never
                for anything of their own.
              </li>
            </LegalList>
          </LegalSection>

          <LegalSection title="Service providers we use">
            <p>
              Turning a saved link into a summary means sending your
              URL, file, or transcript to outside services. Each one
              only sees what it needs for its part of the job, nothing
              more:
            </p>
            <LegalList>
              <li>
                <strong>Google (Gemini)</strong> - transcription,
                summarization, tagging, OCR, and embeddings.
              </li>
              <li>
                <strong>Google (Drive, Sheets, Cloud Storage)</strong>{' '}
                - storing your results, if you&apos;ve connected your
                Google account (see &quot;What we collect&quot;
                above).
              </li>
              <li>
                <strong>Jina AI</strong> - fetching and parsing
                article pages you submit.
              </li>
              <li>
                <strong>Brave Search</strong> - extra web search we
                use while enriching some jobs.
              </li>
              <li>
                <strong>GitHub</strong> - reading repository content
                for repos you submit.
              </li>
              <li>
                <strong>The source platform itself</strong> (YouTube,
                TikTok, Instagram, etc.) - fetching the
                video/transcript you linked to.
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

          <LegalSection title="Deleting your data">
            <p>
              Deleting a job or a Brain link pulls it from the
              dashboard right away and queues a background cleanup of
              the underlying files: a job&apos;s cleanup covers Drive,
              Cloud Storage, and Sheets, while a Brain link&apos;s
              cleanup covers its Drive file. That cleanup is
              best-effort: on a rare provider-side failure, a cloud
              artifact can outlive the record you deleted. There&apos;s no single
              &quot;delete my account&quot; button yet - delete jobs
              and links one at a time, or email me (see Contact) for a
              full account wipe.
            </p>
          </LegalSection>

          <LegalSection title="Functional preview cookies">
            <p>
              Ownix may set a session cookie named{' '}
              <code>ownix_preview</code> to keep the read-only preview
              active while you browse. It does not identify you or
              track you across sites.
            </p>
          </LegalSection>

          <LegalSection title="Revoking access">
            <p>
              Send <code>/disconnect</code> to the bot at any time to
              revoke your Google connection - this deletes your stored
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
