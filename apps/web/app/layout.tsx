import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { SiteChrome } from "@/components/SiteChrome";

export const metadata: Metadata = {
  title: "DeepSight — Verify the evidence",
  description: "A research workspace for reproducible transit analysis and GenLayer evidence review. Protocol review is not scientific confirmation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@420;520;600&display=swap"
          rel="stylesheet"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: "try{if(localStorage.getItem('deepsight-theme')==='paper')document.documentElement.dataset.theme='paper'}catch(e){}",
          }}
        />
      </head>
      <body suppressHydrationWarning>
        <Providers>
          <SiteChrome>{children}</SiteChrome>
        </Providers>
      </body>
    </html>
  );
}
