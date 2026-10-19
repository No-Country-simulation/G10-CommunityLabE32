import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import Topbar from "@/components/Topbar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CommunityLab",
  description: "Plataforma de métricas e IA",
};

const temaInicial = `(function(){try{document.documentElement.dataset.theme=localStorage.getItem('theme')||'light'}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="relative z-0 min-h-full flex flex-col bg-background text-foreground pb-16 md:pb-0">
        <Script
          id="tema-inicial"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: temaInicial }}
        />

        {/* Marca de agua centrada con el PNG correcto */}
        <div aria-hidden className="pointer-events-none fixed inset-0 z-0 flex items-center justify-center overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/comunity.png"
            alt=""
            className="watermark-logo w-[480px] h-[480px] object-contain select-none"
          />
        </div>

        <Topbar />
        <div className="relative z-10 flex-1 flex flex-col">
          {children}
        </div>
      </body>
    </html>
  );
}