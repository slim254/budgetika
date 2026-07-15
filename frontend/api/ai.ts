import { axiosInstance } from "@/api/axiosInstance";
import { ImportCategorizeResponse } from "@/models/wallets";

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

// AI auto-categorization for CSV import. `formData` carries file, column_mapping,
// amount_config, and filters — the same shape the execute step builds.
export const suggestImportCategories = (walletId: string, formData: FormData) =>
  axiosInstance.post<ImportCategorizeResponse>(
    `wallets/${walletId}/import/categorize/`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
