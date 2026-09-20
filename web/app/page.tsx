import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import { SITE_URL } from '@/lib/site-url';
import { LandingNav } from '@/components/landing/landing-nav';
import { Hero } from '@/components/landing/hero';
import { OnboardingSection } from '@/components/landing/onboarding-section';
import { ShowcaseTranscriptSection } from '@/components/landing/showcase-transcript-section';
import { ShowcaseChecklistSection } from '@/components/landing/showcase-checklist-section';
import { FeaturesSection } from '@/components/landing/features-section';
import { McpSection } from '@/components/landing/mcp-section';
import { CaptureSection } from '@/components/landing/capture-section';
import { SubmissionChannelsSection } from '@/components/landing/submission-channels-section';
import { BrainBanner } from '@/components/landing/brain-banner';
import { StatsSection } from '@/components/landing/stats-section';
import { StorageSection } from '@/components/landing/storage-section';
import { InviteSection } from '@/components/landing/invite-section';
import { LandingFooter } from '@/components/landing/landing-footer';

const pageDescription =
  'Share videos, articles, and repos to Ownix from any app. Three taps, and a minute later the transcript and summary are in your Index - searchable, agent-ready markdown.';

export const metadata: Metadata = {
  title: 'Ownix - Your internet. Own it',
  description: pageDescription,
  alternates: { canonical: SITE_URL },
  openGraph: {
    title: 'Ownix - Your internet. Own it',
    description: pageDescription,
    type: 'website',
    siteName: 'Ownix',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Ownix - Your internet. Own it',
    description: pageDescription,
  },
};

export default async function LandingPage() {
  const signedIn = Boolean((await cookies()).get('vig_session')?.value);
  const telegramBotUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
  const telegramDeepLink = telegramBotUsername
    ? `https://t.me/${telegramBotUsername}`
    : null;

  return (
    <>
      <LandingNav signedIn={signedIn} />

      <main className="bg-canvas text-body">
        <Hero signedIn={signedIn} />
        <OnboardingSection />
        <ShowcaseTranscriptSection />
        <ShowcaseChecklistSection />
        <FeaturesSection />
        <McpSection />
        <CaptureSection />
        <SubmissionChannelsSection telegramDeepLink={telegramDeepLink} />
        <BrainBanner />
        <StatsSection />
        <StorageSection />
        <InviteSection />
      </main>

      <LandingFooter />
    </>
  );
}
