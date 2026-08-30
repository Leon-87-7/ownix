import type { Metadata } from 'next';
import localFont from 'next/font/local';
import './globals.css';
import MockProvider from '@/components/shell/mock-provider';
import SwRegister from '@/components/shell/sw-register';
import { SITE_URL } from '@/lib/site-url';

// Site-wide since it's cheap and every page benefits from rich-result
// eligibility; the private dashboard is noindexed anyway so this is harmless
// weight there.
const softwareAppSchema = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'Ownix',
  url: SITE_URL,
  description: 'Collect what matters. Own your Index. Shape the Brain.',
  applicationCategory: 'ProductivityApplication',
  operatingSystem: 'Web',
};

// Separate from softwareAppSchema (product vs. legal entity) — agent scanners
// and rich results look for Organization specifically for legitimacy/contact
// signals; contactPoint email matches the one on the Privacy/Terms pages.
const organizationSchema = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'Ownix',
  url: SITE_URL,
  contactPoint: {
    '@type': 'ContactPoint',
    email: 'leoneidelman09@gmail.com',
    contactType: 'customer support',
  },
};

// All four self-hosted (fonts/, OFL-licensed, latin-subset) instead of
// next/font/google — Vercel's Turbopack build cache can pin a stale
// fonts.gstatic.com URL that later 404s (Google rotates hashed asset
// URLs), breaking builds with no code change on our side.

// Two voices (DESIGN.md): Inter for human language, JetBrains Mono for
// machine facts. Inter stays a variable font (weights 400/500/600 all used).
const inter = localFont({
  src: './fonts/Inter-Variable.woff2',
  variable: '--font-inter',
  display: 'swap',
});

const jetbrainsMono = localFont({
  src: [
    { path: './fonts/JetBrainsMono-Regular.woff2', weight: '400', style: 'normal' },
    { path: './fonts/JetBrainsMono-Medium.woff2', weight: '500', style: 'normal' },
  ],
  variable: '--font-jetbrains',
  display: 'swap',
});

// Landing-only third and fourth voices (title / subtitle) — the dashboard
// keeps DESIGN.md's two-voice system untouched. Root layout means every
// route's font manifest includes them, so preload:false keeps dashboard
// routes (which never render these) from preloading unused font files.
const montserrat = localFont({
  src: './fonts/Montserrat-SemiBold.woff2',
  weight: '600',
  variable: '--font-montserrat',
  display: 'swap',
  preload: false,
});

const merienda = localFont({
  src: './fonts/Merienda-Medium.woff2',
  weight: '500',
  variable: '--font-merienda',
  display: 'swap',
  preload: false,
});

// Schema objects here are static/env-derived, never user input, but escape
// </script>-breaking chars anyway — cheap and standard for inline JSON-LD.
function jsonLdScript(schema: object): string {
  return JSON.stringify(schema)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026');
}

// new URL() throws on a malformed value (missing protocol, stray whitespace);
// fall back to Vercel's deployment URL rather than crashing metadata resolution.
function siteUrl(): URL | undefined {
  if (!process.env.NEXT_PUBLIC_SITE_URL) return undefined;
  try {
    return new URL(process.env.NEXT_PUBLIC_SITE_URL);
  } catch {
    return undefined;
  }
}

export const metadata: Metadata = {
  // Absolute URLs for og:image etc. Vercel falls back to the deployment URL
  // when this is unset; a custom domain should set NEXT_PUBLIC_SITE_URL.
  ...(siteUrl() ? { metadataBase: siteUrl() } : {}),
  title: 'Ownix - Your internet. Own it',
  description:
    'Collect what matters. Own your Index. Shape the Brain.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} ${montserrat.variable} ${merienda.variable}`}
    >
      <body className="bg-canvas font-sans text-ink antialiased">
        {/* SITE_URL is env/deploy-controlled, not user input, but escape
            </script>-breaking chars anyway — cheap and standard for inline JSON-LD. */}
        {/* nosemgrep -- schema is a static object literal above, not user input; jsonLdScript escapes </script>-breaking chars */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdScript(softwareAppSchema) }}
        />
        {/* nosemgrep -- schema is a static object literal above, not user input; jsonLdScript escapes </script>-breaking chars */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdScript(organizationSchema) }}
        />
        <MockProvider>{children}</MockProvider>
        <SwRegister />
        {/* impeccable-live-start */}
        {process.env.NODE_ENV === 'development' && (
          <script src="http://localhost:8400/live.js" async></script>
        )}
        {/* impeccable-live-end */}
      </body>
    </html>
  );
}
