import { MobileOnboardingStepper } from '@/components/landing/mobile-onboarding-stepper';
import { OnboardingStepper } from '@/components/landing/onboarding-stepper';
import { WordmarkMarquee } from '@/components/landing/wordmark-marquee';

export function OnboardingSection() {
  return (
    <section
      aria-labelledby="onboarding"
      className="border-t border-line py-6"
    >
      <div className="mx-auto max-w-[960px] px-6">
        {/* border-t + NEXT eyebrow on lg: gives the fold a hard stop —
          the onboarding lead-in starts exactly at the fixed-height
          fold's bottom edge instead of visually overlapping the hero
          text above it while the stepper pins. */}
        <div className="hidden sm:block lg:pt-10">
          <h2
            id="onboarding"
            className="scroll-mt-[4.25rem] mb-4 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
          >
            Three taps. Nothing new to learn.
          </h2>
          <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed">
            It&apos;s the share sheet you already use - aimed at Ownix
            instead of a friend. Mid-doomscroll, mid-commute,
            mid-anything.
          </p>
        </div>

        <MobileOnboardingStepper />
        <div className="hidden sm:block">
          <OnboardingStepper />
        </div>
        <div className="mt-6 min-w-0 flex-1 hidden sm:block">
          <WordmarkMarquee />
        </div>
      </div>
    </section>
  );
}
