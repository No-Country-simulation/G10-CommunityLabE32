import type { Metadata } from "next";
import localFont from "next/font/local";
import Script from "next/script";
import Topbar from "@/components/Topbar";
import ReferenciaPublicada from "@/components/ReferenciaPublicada";
import "./globals.css";
import "./gumroad.css";

const communitySans = localFont({
  variable: "--font-community-sans",
  display: "swap",
  src: [
    { path: "./fonts/ABCFavorit-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/ABCFavorit-RegularItalic.woff2", weight: "400", style: "italic" },
    { path: "./fonts/ABCFavorit-Bold.woff2", weight: "700", style: "normal" },
    { path: "./fonts/ABCFavorit-BoldItalic.woff2", weight: "700", style: "italic" },
  ],
});

export const metadata: Metadata = {
  title: "CommunityLab",
  description: "Plataforma de métricas e IA",
};

const temaInicial = `(function(){document.documentElement.lang='es';try{document.documentElement.dataset.theme=localStorage.getItem('communitylab-theme')==='light'?'light':'dark'}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="es"
      translate="yes"
      data-theme="dark"
      suppressHydrationWarning
      className={`${communitySans.variable} h-full antialiased`}
    >
      <body className="relative z-0 min-h-full flex flex-col bg-background text-foreground pb-16 md:pb-0">
        <Script
          id="tema-inicial"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: temaInicial }}
        />

        <Topbar />
        <ReferenciaPublicada />
        <div aria-hidden="true" className="luz-navegacion" />
        <div className="relative z-10 flex-1 flex flex-col">
          {children}
        </div>
      </body>
    </html>
  );
}
