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

const desvanecido = "radial-gradient(closest-side, #000 30%, transparent 100%)";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Script
          id="tema-inicial"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: temaInicial }}
        />

        {/* Marca de agua: logo grande con borde desvanecido, centrado en el área principal */}
        <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.svg"
            alt=""
            className="absolute left-[60%] top-[55%] w-[780px] max-w-none -translate-x-1/2 -translate-y-1/2 opacity-[0.13] blur-[2px]"
            style={{ WebkitMaskImage: desvanecido, maskImage: desvanecido }}
          />
        </div>

        <Topbar />
        {children}
      </body>
    </html>
  );
}