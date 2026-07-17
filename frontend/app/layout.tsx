import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://fon.ptichkin.tech";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "ФОН — удалить фон с фото онлайн | BirdTech",
    template: "%s | ФОН",
  },
  description: "Удаляйте фон с JPG, PNG и WebP онлайн. Прозрачный PNG без регистрации — проект BirdTech.",
  keywords: ["удалить фон", "удаление фона", "прозрачный PNG", "удалить фон с фото", "BirdTech"],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "ru_RU",
    url: "/",
    siteName: "ФОН",
    title: "ФОН — удалить фон с фото онлайн",
    description: "Удаляйте фон с JPG, PNG и WebP онлайн. Прозрачный PNG без регистрации.",
  },
  twitter: {
    card: "summary",
    title: "ФОН — удалить фон с фото онлайн",
    description: "Быстрое удаление фона с фотографий — проект BirdTech.",
  },
  robots: { index: true, follow: true },
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
