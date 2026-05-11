"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Wallet as WalletIcon, TrendingUp, TrendingDown, Scale } from "lucide-react";
import { DashboardSummary } from "@/models/wallets";
import { formatCurrency } from "@/lib/currency";

interface MetricsSummaryCardsProps {
  summary: DashboardSummary;
  walletCount: number;
}

export function MetricsSummaryCards({ summary, walletCount }: MetricsSummaryCardsProps) {
  const totalBalance = Number(summary.total_balance);
  const income = Number(summary.total_income_this_month);
  const expenses = Number(summary.total_expenses_this_month);
  const net = Number(summary.net_this_month);

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Balance</CardTitle>
          <WalletIcon className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${totalBalance >= 0 ? "text-green-600" : "text-red-600"}`}>
            {formatCurrency(totalBalance)}
          </div>
          <p className="text-xs text-muted-foreground">
            Across {walletCount} wallet{walletCount !== 1 ? "s" : ""}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Income (this month)</CardTitle>
          <TrendingUp className="h-4 w-4 text-green-600" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-green-600">{formatCurrency(income)}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Expenses (this month)</CardTitle>
          <TrendingDown className="h-4 w-4 text-red-600" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-red-600">{formatCurrency(expenses)}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Net (this month)</CardTitle>
          <Scale className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${net >= 0 ? "text-green-600" : "text-red-600"}`}>
            {net >= 0 ? "+" : ""}{formatCurrency(net)}
          </div>
          <p className="text-xs text-muted-foreground">Income − Expenses</p>
        </CardContent>
      </Card>
    </div>
  );
}
