import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import MockProvider from "@/components/MockProvider";

// Two voices (DESIGN.md): Inter for human language, JetBrains Mono for machine facts.
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains",
  display: "swap",
});

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
  title: "Ownix — Your internet, indexed",
  description:
    "Collect what matters. Own your Index. Shape the Brain.",
  icons: {
    icon: "/icon0.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-canvas font-sans text-ink antialiased">
        <MockProvider>{children}</MockProvider>
      {/* impeccable-live-start */}
{process.env.NODE_ENV === 'development' && <script src="http://localhost:8400/live.js"></script>}
{/* impeccable-live-end */}
</body>
    </html>
  );
}
