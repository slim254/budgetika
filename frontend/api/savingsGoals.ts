import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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

// React Query hooks

export const useSavingsGoals = (walletId: string) =>
  useQuery({
    queryKey: ["savings-goals", walletId],
    queryFn: () => savingsGoalsAPI.listGoals(walletId),
  });

export const useMonthlySummary = (
  walletId: string,
  month?: number,
  year?: number
) =>
  useQuery({
    queryKey: ["savings-summary", walletId, month, year],
    queryFn: () => savingsGoalsAPI.getMonthlySummary(walletId, month, year),
  });

export const useCreateGoal = (walletId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (
      data: Omit<SavingsGoal, "id" | "created_at" | "status" | "monthly_needed">
    ) => savingsGoalsAPI.createGoal(walletId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["savings-goals", walletId],
      });
      queryClient.invalidateQueries({
        queryKey: ["savings-summary", walletId],
      });
    },
  });
};

export const useUpdateGoal = (walletId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      goalId,
      data,
    }: {
      goalId: string;
      data: Partial<
        Omit<SavingsGoal, "id" | "created_at" | "status" | "monthly_needed">
      >;
    }) => savingsGoalsAPI.updateGoal(walletId, goalId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["savings-goals", walletId],
      });
      queryClient.invalidateQueries({
        queryKey: ["savings-summary", walletId],
      });
    },
  });
};

export const useDeleteGoal = (walletId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (goalId: string) =>
      savingsGoalsAPI.deleteGoal(walletId, goalId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["savings-goals", walletId],
      });
      queryClient.invalidateQueries({
        queryKey: ["savings-summary", walletId],
      });
    },
  });
};
