import type { Metadata } from "next";
import "@fontsource-variable/newsreader";
import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "@fontsource/jetbrains-mono/400.css";
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
        <script
          dangerouslySetInnerHTML={{
            __html: "try{if(localStorage.getItem('deepsight-theme')==='observation')document.documentElement.dataset.theme='observation'}catch(e){}",
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
