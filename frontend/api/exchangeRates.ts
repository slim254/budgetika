import { axiosInstance } from "./axiosInstance";
import { Currency } from "@/models/wallets";

export interface ExchangeRateResponse {
  rate: string;
  date: string;
}

export async function getExchangeRate(
  base: Currency,
  quote: Currency,
  date?: string,
): Promise<ExchangeRateResponse> {
  const params: Record<string, string> = { base, quote };
  if (date) params.date = date;
  const response = await axiosInstance.get<ExchangeRateResponse>("exchange-rates/", { params });
  return response.data;
}
