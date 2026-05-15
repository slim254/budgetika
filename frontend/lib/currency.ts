import { Currency } from "@/models/wallets";

const CURRENCY_PREFIX: Record<Currency, string> = {
  usd: "$",
  eur: "€",
  gbp: "£",
  pln: "PLN ",
};

export function formatCurrency(
  amount: number | string,
  currency?: Currency
): string {
  const n = Number(amount);
  const abs = Math.abs(n).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const sign = n < 0 ? "-" : "";
  const prefix = currency ? CURRENCY_PREFIX[currency] : "";
  return `${sign}${prefix}${abs}`;
}

export function getLocaleCurrency(): Currency {
  const lang = navigator.language.toLowerCase();
  if (lang.startsWith("pl")) return "pln";
  if (lang === "en-gb") return "gbp";
  if (
    lang.startsWith("de") ||
    lang.startsWith("fr") ||
    lang.startsWith("es") ||
    lang.startsWith("it") ||
    lang.startsWith("pt")
  )
    return "eur";
  return "usd";
}
