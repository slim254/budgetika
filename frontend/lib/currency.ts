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
