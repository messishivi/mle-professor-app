import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";

export const metadata: Metadata = {
  title: {
    default: "MLE Professor",
    template: "%s · MLE Professor",
  },
  description:
    "Daily ML paper pulse and a grounded consultant for working MLEs.",
};

// Sets data-theme before first paint (reads localStorage) — first child of
// <body> so it runs while the document parses, avoiding a theme flash.
const themeInitScript = `(function(){try{if(localStorage.getItem("mle-theme")==="light"){document.documentElement.setAttribute("data-theme","light");}}catch(e){}})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="flex min-h-dvh flex-col font-sans antialiased">
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <Nav />
        <main className="mx-auto w-full max-w-[1200px] flex-1 px-6 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
