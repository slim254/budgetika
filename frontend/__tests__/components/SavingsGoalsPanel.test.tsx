import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SavingsGoalsPanel } from "@/components/SavingsGoalsPanel";
import * as api from "@/api/savingsGoals";

// Mock the API
jest.mock("@/api/savingsGoals");

const mockGoals: api.SavingsGoal[] = [
  {
    id: "1",
    name: "Vacation",
    target_amount: "500",
    target_date: "2026-06-15",
    status: "active",
    monthly_needed: "250",
    created_at: "2026-05-16T00:00:00Z",
  },
  {
    id: "2",
    name: "Insurance",
    target_amount: "1200",
    target_date: "2026-12-31",
    status: "active",
    monthly_needed: "200",
    created_at: "2026-05-16T00:00:00Z",
  },
];

const mockSummary: api.MonthlySummary = {
  month: 5,
  year: 2026,
  total_monthly_needed: "450",
  actual_savings: "500",
  difference: "50",
  status: "on_track",
  goals: mockGoals,
};

describe("SavingsGoalsPanel", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    (api.useSavingsGoals as jest.Mock).mockReturnValue({
      data: mockGoals,
      isLoading: false,
    });
    (api.useMonthlySummary as jest.Mock).mockReturnValue({
      data: mockSummary,
    });
    (api.useDeleteGoal as jest.Mock).mockReturnValue({
      mutateAsync: jest.fn(),
    });
  });

  it("renders goals list", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(screen.getByText("Vacation")).toBeInTheDocument();
    expect(screen.getByText("Insurance")).toBeInTheDocument();
  });

  it("displays summary card when goals exist", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(screen.getByText("Monthly Savings Target")).toBeInTheDocument();
    expect(screen.getByText("USD 450")).toBeInTheDocument();
    expect(screen.getByText("USD 500")).toBeInTheDocument();
  });

  it("shows on-track status when actual >= needed", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(screen.getByText("On Track")).toBeInTheDocument();
  });

  it("shows short status when actual < needed", () => {
    (api.useMonthlySummary as jest.Mock).mockReturnValue({
      data: { ...mockSummary, status: "short", difference: "-50" },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(screen.getByText("Short")).toBeInTheDocument();
  });

  it("shows empty state when no goals", () => {
    (api.useSavingsGoals as jest.Mock).mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(
      screen.getByText(/No savings goals yet/)
    ).toBeInTheDocument();
  });

  it("opens dialog when add goal is clicked", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    const addButton = screen.getByText("Add Goal");
    fireEvent.click(addButton);

    expect(
      screen.getByText("Create Savings Goal")
    ).toBeInTheDocument();
  });
});
