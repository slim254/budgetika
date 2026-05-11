"use client";

import { axiosInstance } from "@/api/axiosInstance";
import ProtectedRoute from "@/components/ProtectedRoute";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, TrendingUp, TrendingDown, ListChecks } from "lucide-react";
import { DynamicIcon } from "@/components/IconPicker";
import { UserMenu } from "@/components/UserMenu";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { WalletMetricsResponse } from "@/models/wallets";
import { CategoryBreakdown } from "@/components/CategoryBreakdown";

interface MetricStatProps {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "positive" | "negative";
}

function MetricStat({ label, value, hint, tone = "default" }: MetricStatProps) {
  const toneClass =
    tone === "positive" ? "text-green-600" : tone === "negative" ? "text-red-600" : "";
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${toneClass}`}>{value}</div>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}

export default function WalletMetricsPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<WalletMetricsResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!params.id) return;
    setIsLoading(true);
    axiosInstance
      .get<WalletMetricsResponse>(`wallets/${params.id}/metrics/`)
      .then((r) => setData(r.data))
      .catch((err) => console.error("Failed to fetch wallet metrics:", err))
      .finally(() => setIsLoading(false));
  }, [params.id]);

  if (isLoading && !data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <p className="text-gray-500">Loading metrics…</p>
        </div>
      </ProtectedRoute>
    );
  }

  if (!data) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <p className="text-gray-500">Could not load wallet metrics.</p>
        </div>
      </ProtectedRoute>
    );
  }

  const balance = Number(data.balance);
  const m = data.metrics;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex justify-between items-center mb-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push(`/wallet/${params.id}`)}
              >
                <ArrowLeft className="mr-2 h-4 w-4" /> Back to wallet
              </Button>
              <UserMenu />
            </div>
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">{data.wallet_name}</h1>
                <p className="text-sm text-gray-500">
                  Metrics · Currency: {data.currency.toUpperCase()}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-500">Current Balance</p>
                <p className={`text-3xl font-bold ${balance >= 0 ? "text-green-600" : "text-red-600"}`}>
                  ${balance.toFixed(2)}
                </p>
              </div>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
          <section>
            <h2 className="text-lg font-semibold mb-3">This month</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <MetricStat
                label="Income"
                value={`$${Number(m.income_this_month).toFixed(2)}`}
                tone="positive"
              />
              <MetricStat
                label="Expenses"
                value={`$${Number(m.expenses_this_month).toFixed(2)}`}
                tone="negative"
              />
              <MetricStat
                label="Net"
                value={`${Number(m.net_this_month) >= 0 ? "+" : ""}$${Number(m.net_this_month).toFixed(2)}`}
                tone={Number(m.net_this_month) >= 0 ? "positive" : "negative"}
              />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3">Lifetime</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <MetricStat
                label="Total Transactions"
                value={String(m.total_transactions)}
                hint={`${m.income_count} income · ${m.expense_count} expense`}
              />
              <MetricStat
                label="Average Transaction"
                value={`$${Number(m.average_transaction).toFixed(2)}`}
              />
              <MetricStat
                label="Largest Income"
                value={`$${Number(m.largest_income).toFixed(2)}`}
                tone="positive"
              />
              <MetricStat
                label="Largest Expense"
                value={`$${Number(m.largest_expense).toFixed(2)}`}
                tone="negative"
              />
            </div>
          </section>

          <CategoryBreakdown
            data={data.category_breakdown}
            title="Spending by Category"
            description="All-time"
          />

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ListChecks className="h-5 w-5 text-muted-foreground" />
                Recent Transactions
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.recent_transactions.length === 0 ? (
                <p className="text-sm text-gray-500 py-4 text-center">No transactions yet.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Note</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.recent_transactions.map((t) => {
                      const isIncome = Number(t.amount) > 0;
                      return (
                        <TableRow key={t.id}>
                          <TableCell className="whitespace-nowrap text-sm text-gray-600">
                            {new Date(t.date).toLocaleDateString()}
                          </TableCell>
                          <TableCell className="font-medium">{t.note}</TableCell>
                          <TableCell>
                            {t.category ? (
                              <span className="inline-flex items-center gap-2">
                                <span
                                  className="inline-flex h-6 w-6 items-center justify-center rounded-md"
                                  style={{
                                    backgroundColor: t.category.color + "20",
                                    color: t.category.color,
                                  }}
                                >
                                  <DynamicIcon name={t.category.icon} className="h-3.5 w-3.5" />
                                </span>
                                <span className="text-sm">{t.category.name}</span>
                              </span>
                            ) : (
                              <span className="text-sm text-gray-400">—</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <span
                              className={`inline-flex items-center gap-1 font-semibold ${
                                isIncome ? "text-green-600" : "text-red-600"
                              }`}
                            >
                              {isIncome ? (
                                <TrendingUp className="h-3.5 w-3.5" />
                              ) : (
                                <TrendingDown className="h-3.5 w-3.5" />
                              )}
                              {isIncome ? "+" : ""}${Number(t.amount).toFixed(2)}
                            </span>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </main>
      </div>
    </ProtectedRoute>
  );
}
