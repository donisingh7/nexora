import type { Metadata } from "next";
import "./globals.css";

import { ToastProvider } from "@/components/Toast";

export const metadata: Metadata = {
  title: "Nexora | Enterprise Knowledge Intelligence",
  description: "A foundation for organizational knowledge and grounded answers.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
