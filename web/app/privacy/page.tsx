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
            updated="Last updated: August 23, 2026"
          />

          <p>
            Ownix is a quiet tool for collecting the internet you care
            about. Saved videos, links, articles, repos, documents,
            and ideas become part of your personal Index - private to
            you; see &quot;Your Brain is private&quot; below.
          </p>

          <LegalSection title="Who controls this data">
            <p>
              Ownix is operated by Leon Eidelman, an individual based
              in Israel. Leon Eidelman is the controller of the
              personal information described in this policy. This
              policy is governed by the laws of the State of Israel.
              Contact for anything below:{' '}
              <LegalLink href="mailto:leoneidelman09@gmail.com">
                leoneidelman09@gmail.com
              </LegalLink>
              .
            </p>
          </LegalSection>

          <LegalSection title="What we collect">
            <LegalList>
              <li>
                Your Telegram identity (chat ID, name, username, and
                profile photo URL) - used to identify your account and
                route your data. Required: Ownix is a Telegram bot, so
                there is no way to use it without this.
              </li>
              <li>
                The email address you provide for invite approval,
                plus your access status (<code>pending</code>,{' '}
                <code>approved</code>, or <code>blocked</code>).
                Required to be considered for access while Ownix is
                invite-only; if you don&apos;t provide one your
                request stays pending and unreviewed.
              </li>
              <li>
                Links and documents you save, the analysis Ownix
                generates from them (transcripts, descriptions, tags,
                summaries), and your job history - what you submitted
                and when. Kept until you delete the job or link
                yourself, or delete your account; see &quot;Deleting
                your data&quot; and &quot;Deleting your account&quot;
                below.
              </li>
              <li>
                A numeric embedding (a similarity fingerprint, not
                human-readable text) generated from each saved item&apos;s
                content, to power your own search and link graph. See
                &quot;Your Brain is private&quot; below for who can see
                this.
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
                create with it. Optional - Ownix works without it.
              </li>
            </LegalList>
            <p>
              Content you submit (a video, article, repo, or document)
              can itself contain personal information about other
              people, not just you - a name mentioned in a transcript,
              a face in a photo. Ownix processes that content the same
              way it processes anything else you submit; it does not
              try to detect or specially handle third-party personal
              data inside it.
            </p>
          </LegalSection>

          <LegalSection title="Your Brain is private">
            <p>
              Your Index and Second Brain (the link graph on the Brain
              page) are private to your Telegram account. Nobody else
              using Ownix can see your saved links, titles,
              descriptions, tags, or embeddings - every read and write
              is scoped to your own account. There is currently no
              feature that shares your saved items with other users.
            </p>
          </LegalSection>

          <LegalSection title="How AI processes your content">
            <p>
              Google&apos;s Gemini API does the actual work: transcribing
              video, describing images, pulling text off photos (OCR),
              and writing the summaries, tags, and embeddings you see
              in your Feed and Brain. Whatever you submit - a URL, a
              file, a transcript - gets sent to Gemini to make that
              happen. We use the standard Gemini API (not Google
              Cloud&apos;s Vertex AI); Google&apos;s current Gemini API
              Additional Terms of Service govern how Google may use
              that data on their end, and we&apos;d rather point you at
              those live terms than promise something we can&apos;t
              enforce on Google&apos;s infrastructure.
            </p>
          </LegalSection>

          <LegalSection title="How we use approval email">
            <p>
              Ownix is invite-only while it is young. We use the
              approval email to review access requests, associate the
              request with your Telegram account, and contact you
              about access if needed - this part is not optional while
              your account is pending.
            </p>
            <p>
              <span className="border-b border-dashed border-muted pb-0.5 font-medium text-body">
                Ownix is shaped with the people using it.
              </span>{' '}
              Separately, and only with approved accounts, we may use
              this email to ask for feedback, discuss feature
              improvements, and share Ownix product updates. These are
              manual, one-off emails from a real person - not an
              automated mailing list, and not yet backed by a
              suppression list. Tell us at the contact above if
              you&apos;d rather not get these and we&apos;ll do our
              best to honor it going forward; it never affects your
              access.
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
                We never sell your data. We send it to the providers
                below only to get your job done, each scoped to what
                that step of the job needs.
              </li>
            </LegalList>
          </LegalSection>

          <LegalSection title="Service providers we use">
            <p>
              Turning a saved link into a summary means sending your
              URL, file, or transcript to outside services, each
              scoped to what its part of the job needs:
            </p>
            <LegalList>
              <li>
                <strong>Google (Gemini API)</strong> - transcription,
                summarization, tagging, OCR, and embeddings, the same
                model already doing this work everywhere else in
                Ownix, so your content isn&apos;t routed through a
                second AI vendor just for this.
              </li>
              <li>
                <strong>Google Drive and Sheets</strong> - if you&apos;ve
                connected your Google account (see &quot;What we
                collect&quot; above), Ownix writes results into
                <em> your own</em> Drive and Sheets - your account, not
                a shared Ownix datastore, so you keep the copy and the
                access.
              </li>
              <li>
                <strong>Google Cloud Storage</strong> - separate from
                the above: Ownix-operated infrastructure, not part of
                your Google account, used to hold document pipeline
                artifacts (uploaded PDFs and their extracted text)
                while a job runs. Removed when you delete the job; see
                &quot;Deleting your data&quot; below.
              </li>
              <li>
                <strong>Jina AI</strong> - fetching and parsing
                article pages you submit, rendering JS-heavy pages and
                stripping out ads and navigation chrome so you get the
                article, not the page around it.
              </li>
              <li>
                <strong>Brave Search</strong> - extra web search we
                use while enriching some jobs, run through an
                independent index rather than Google&apos;s, so
                enrichment isn&apos;t tied to the same company already
                handling your AI processing and storage.
              </li>
              <li>
                <strong>GitHub</strong> - reading repository content
                for repos you submit, since that&apos;s where the repo
                you linked to actually lives.
              </li>
              <li>
                <strong>The source platform itself</strong> (YouTube,
                TikTok, Instagram, etc.) - fetching the
                video/transcript you linked to, the origin of what you
                saved.
              </li>
            </LegalList>
            <p>
              Our use of information from Google Workspace APIs (Drive,
              Sheets) adheres to the{' '}
              <LegalLink href="https://developers.google.com/terms/api-services-user-data-policy">
                Google API Services User Data Policy
              </LegalLink>
              , including its Limited Use requirements.
            </p>
          </LegalSection>

          <LegalSection title="International data transfers">
            <p>
              Ownix is operated from Israel, but the providers above
              (Google, Jina AI, Brave, GitHub, and the platform a link
              came from) process data on their own infrastructure,
              which may be outside Israel. Sending your content to
              them for processing is how Ownix does its job; we
              don&apos;t control where each provider locates its
              servers.
            </p>
          </LegalSection>

          <LegalSection title="How your data is stored">
            <p>
              Video analysis results, job history, links, and
              embeddings are stored in a private SQLite database
              scoped to your Telegram account. Document pipeline
              artifacts live in the Cloud Storage bucket described
              above. Your Google OAuth token, if you connect one, is
              stored encrypted and used only to write your own results
              to your own Drive/Sheets.
            </p>
          </LegalSection>

          <LegalSection title="How long we keep it">
            <p>
              Jobs, links, and embeddings: kept until you delete them
              individually, or delete your account (see below). Your
              Google OAuth token: kept until you disconnect or delete
              your account. Your invite-approval email and status: kept
              while your account exists. Operational logs (request and
              error logs used for debugging and abuse prevention): kept
              only as long as needed for that purpose, then rotated
              out.
            </p>
          </LegalSection>

          <LegalSection title="Deleting your data">
            <p>
              Deleting a job or a Brain link pulls it from the
              dashboard right away - the database record, embedding,
              transcript, and tags are gone immediately. That same
              action queues a background cleanup of the underlying
              cloud files: a job&apos;s cleanup covers Drive, Cloud
              Storage, and Sheets, while a Brain link&apos;s cleanup
              covers its Drive file. That cloud cleanup step is
              best-effort: on a rare provider-side failure, a cloud
              artifact can outlive the record you deleted, though the
              database record itself is already gone. Delete jobs and
              links one at a time from the dashboard, or delete your
              whole account at once - see below.
            </p>
          </LegalSection>

          <LegalSection title="Deleting your account">
            <p>
              Settings &rarr; Danger zone &rarr; Delete my account
              permanently removes, immediately: every job, every Brain
              link and its embedding, your tags and domain rules, your
              Chrome extension tokens, your Google connection (the
              stored token is deleted and revoked with Google), and
              your account record itself. Your session ends at the
              same time. Cloud artifacts behind those jobs and links
              (Drive files, Cloud Storage objects, Sheets rows) are
              queued for best-effort cleanup the same way individual
              deletes work, described above. This cannot be undone.
            </p>
          </LegalSection>

          <LegalSection title="Your rights">
            <p>
              Whether or not you&apos;re in Israel, you can ask us
              (contact above) to:
            </p>
            <LegalList>
              <li>
                Access a copy of the personal information we hold
                about you - most of it is already visible in your own
                dashboard (Feed, Brain, Controls).
              </li>
              <li>Correct information that&apos;s wrong or outdated.</li>
              <li>
                Delete your data - self-serve via Settings &rarr;
                Danger zone, or ask us to do it for you.
              </li>
              <li>
                Object to, or ask us to stop, a specific use of your
                data (e.g. product-update emails - see &quot;How we
                use approval email&quot; above).
              </li>
              <li>
                Withdraw consent for anything we process on that
                basis, and revoke your Google authorization at any
                time (see &quot;Revoking access&quot; below).
              </li>
            </LegalList>
            <p>
              We&apos;ll respond as quickly as we reasonably can - this
              is currently a one-person operation, so treat any
              timeline as best-effort rather than a guaranteed SLA.
            </p>
          </LegalSection>

          <LegalSection title="Security">
            <p>
              We use reasonable technical safeguards for the data
              above: encryption in transit (HTTPS) to every provider
              listed, your Google OAuth token encrypted at rest,
              access scoped per Telegram account in the database and
              API, and Google API credentials restricted to the
              specific scopes listed in &quot;What we collect.&quot;
            </p>
          </LegalSection>

          <LegalSection title="Children">
            <p>
              Ownix is not intended for, and we do not knowingly
              collect information from, anyone under 18.
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

          <LegalSection title="Changes to this policy">
            <p>
              If how Ownix handles your data changes materially -
              including a new feature that shares data across
              users - we&apos;ll update this page and change the date
              at the top. For a change to how we use data from Google
              APIs specifically, we&apos;ll notify you and, where
              required, ask again before the new use begins.
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
