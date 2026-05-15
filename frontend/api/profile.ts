import { axiosInstance } from "./axiosInstance";
import { Currency } from "@/models/wallets";

export interface UserProfile {
  preferred_currency: Currency | null;
}

export async function getProfile(): Promise<UserProfile> {
  const response = await axiosInstance.get<UserProfile>("profile/");
  return response.data;
}

export async function patchProfile(preferred_currency: Currency): Promise<UserProfile> {
  const response = await axiosInstance.patch<UserProfile>("profile/", { preferred_currency });
  return response.data;
}
