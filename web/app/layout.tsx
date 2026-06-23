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

export const metadata: Metadata = {
  title: "vig — Video Intelligence Gateway",
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
      </body>
    </html>
  );
}
