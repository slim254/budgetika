import { axiosInstance } from "@/api/axiosInstance";
import {
  BudgetRule,
  BudgetRuleFormData,
  BudgetMonthOverride,
  BudgetOverrideFormData,
  BudgetSummaryItem,
} from "@/models/wallets";

export const getBudgetSummary = (walletId: string, month: number, year: number) =>
  axiosInstance.get<BudgetSummaryItem[]>(
    `wallets/${walletId}/budgets/summary/?month=${month}&year=${year}`
  );

export const getBudgetRules = (walletId: string) =>
  axiosInstance.get<BudgetRule[]>(`wallets/${walletId}/budgets/`);

export const createBudgetRule = (walletId: string, data: BudgetRuleFormData) =>
  axiosInstance.post<BudgetRule>(`wallets/${walletId}/budgets/`, data);

export const updateBudgetRule = (
  walletId: string,
  ruleId: string,
  data: Partial<BudgetRuleFormData>
) => axiosInstance.patch<BudgetRule>(`wallets/${walletId}/budgets/${ruleId}/`, data);

export const deleteBudgetRule = (walletId: string, ruleId: string) =>
  axiosInstance.delete(`wallets/${walletId}/budgets/${ruleId}/`);

export const upsertBudgetOverride = (walletId: string, data: BudgetOverrideFormData) =>
  axiosInstance.post<BudgetMonthOverride>(`wallets/${walletId}/budgets/overrides/`, data);

export const deleteBudgetOverride = (walletId: string, overrideId: string) =>
  axiosInstance.delete(`wallets/${walletId}/budgets/overrides/${overrideId}/`);
