import { axiosInstance } from "@/api/axiosInstance";

export interface SavingsGoal {
  id: string;
  name: string;
  target_amount: string;
  target_date: string;
  status: "active" | "completed" | "missed";
  monthly_needed: string;
  created_at: string;
}

export interface MonthlySummary {
  month: number;
  year: number;
  total_monthly_needed: string;
  actual_savings: string;
  difference: string;
  status: "on_track" | "short";
  goals: SavingsGoal[];
}

export const savingsGoalsAPI = {
  // List all goals for a wallet
  listGoals: (walletId: string) =>
    axiosInstance.get<SavingsGoal[]>(`wallets/${walletId}/goals/`),

  // Create a new goal
  createGoal: (
    walletId: string,
    data: Omit<SavingsGoal, "id" | "created_at" | "status" | "monthly_needed">
  ) => axiosInstance.post<SavingsGoal>(`wallets/${walletId}/goals/`, data),

  // Update an existing goal
  updateGoal: (
    walletId: string,
    goalId: string,
    data: Partial<
      Omit<SavingsGoal, "id" | "created_at" | "status" | "monthly_needed">
    >
  ) =>
    axiosInstance.patch<SavingsGoal>(
      `wallets/${walletId}/goals/${goalId}/`,
      data
    ),

  // Delete a goal
  deleteGoal: (walletId: string, goalId: string) =>
    axiosInstance.delete(`wallets/${walletId}/goals/${goalId}/`),

  // Get monthly summary
  getMonthlySummary: (walletId: string, month?: number, year?: number) => {
    const params = new URLSearchParams();
    if (month) params.append("month", month.toString());
    if (year) params.append("year", year.toString());
    const queryString = params.toString();
    const url = queryString
      ? `wallets/${walletId}/goals/summary/?${queryString}`
      : `wallets/${walletId}/goals/summary/`;
    return axiosInstance.get<MonthlySummary>(url);
  },
};
