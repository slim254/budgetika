import { axiosInstance } from "@/api/axiosInstance";

export interface CategorySuggestion {
  id: string;
  name: string;
}

export interface CategorizeResponse {
  suggestion: CategorySuggestion | null;
  usage_warning: { percent_used: number; threshold: number } | null;
}

export const categorizeNote = (note: string) =>
  axiosInstance.post<CategorizeResponse>("wallets/categorize/", { note });
