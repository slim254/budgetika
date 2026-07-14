"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Settings } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { BudgetSummaryItem, Currency } from "@/models/wallets";
import { getBudgetSummary } from "@/api/budgets";
import { DynamicIcon } from "@/components/IconPicker";
import { formatCurrency } from "@/lib/currency";

interface BudgetPanelProps {
  walletId: string;
  month: number;
  year: number;
  currency: Currency;
  onManageClick: () => void;
}

export function BudgetPanel({ walletId, month, year, currency, onManageClick }: BudgetPanelProps) {
  const storageKey = `budget-panel-${walletId}`;

  const [expanded, setExpanded] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(storageKey) === "true";
  });
  const [summary, setSummary] = useState<BudgetSummaryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const overBudget = summary.filter((i) => i.is_over_budget);
  const toastedKey = useRef<string>("");

  const fetchSummary = useCallback(() => {
    setLoading(true);
    setError(null);
    getBudgetSummary(walletId, month, year)
      .then((res) => setSummary(res.data))
      .catch(() => setError("Failed to load budget summary."))
      .finally(() => setLoading(false));
  }, [walletId, month, year]);

  useEffect(() => {
    localStorage.setItem(storageKey, String(expanded));
  }, [expanded, storageKey]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    const key = `${walletId}-${year}-${month}`;
    if (overBudget.length > 0 && toastedKey.current !== key) {
      toastedKey.current = key;
      toast.error(
        overBudget.length === 1
          ? `Over budget: ${overBudget[0].category.name}`
          : `${overBudget.length} categories over budget`
      );
    }
  }, [overBudget, walletId, year, month]);

  const toggle = () => setExpanded((e) => !e);

  return (
    <Card className="mb-6">
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <button
            onClick={toggle}
            className="flex items-center gap-2 text-sm font-medium hover:text-gray-700"
            aria-expanded={expanded}
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
            Budget
            {overBudget.length > 0 && (
              <span className="ml-1 inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                {overBudget.length} over
              </span>
            )}
          </button>
          <Button variant="ghost" size="sm" onClick={onManageClick}>
            <Settings className="h-4 w-4 mr-1" />
            Manage budgets
          </Button>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="pt-0">
          {loading && <p className="text-sm text-gray-500 py-2">Loading...</p>}

          {error && (
            <div className="flex items-center gap-2 py-2">
              <p className="text-sm text-red-600">{error}</p>
              <Button variant="ghost" size="sm" onClick={fetchSummary}>
                Retry
              </Button>
            </div>
          )}

          {!loading && !error && summary.length === 0 && (
            <p className="text-sm text-gray-500 py-2">
              No budgets set — click Manage budgets to add one.
            </p>
          )}

          {!loading && !error && summary.length > 0 && (
            <div className="space-y-4">
              {summary.map((item) => {
                const limit = Number(item.limit);
                const pct = limit > 0
                  ? Math.min(100, (Number(item.spent) / limit) * 100)
                  : 0;
                return (
                  <div key={item.category.id}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2 text-sm">
                        <div
                          className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: item.category.color + "20" }}
                        >
                          <DynamicIcon
                            name={item.category.icon || "circle"}
                            className="h-3 w-3"
                            style={{ color: item.category.color }}
                          />
                        </div>
                        <span>{item.category.name}</span>
                        {item.is_override && (
                          <span className="text-xs text-gray-400">(override)</span>
                        )}
                      </div>
                      <span className="text-sm text-gray-600 ml-2 whitespace-nowrap">
                        {formatCurrency(item.spent, currency)} /{" "}
                        {formatCurrency(item.limit, currency)}
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${
                          item.is_over_budget ? "bg-red-500" : "bg-blue-500"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p
                      className={`text-xs mt-1 ${
                        item.is_over_budget ? "text-red-600 font-medium" : "text-gray-500"
                      }`}
                    >
                      {item.is_over_budget
                        ? `${formatCurrency(
                            Math.abs(Number(item.remaining)),
                            currency
                          )} over budget`
                        : `${formatCurrency(item.remaining, currency)} remaining`}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
