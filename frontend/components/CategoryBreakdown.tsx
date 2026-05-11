"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DynamicIcon } from "@/components/IconPicker";
import { CategorySpending, Currency } from "@/models/wallets";
import { PieChart as PieChartIcon } from "lucide-react";
import { formatCurrency } from "@/lib/currency";

interface CategoryBreakdownProps {
  data: CategorySpending[];
  title?: string;
  description?: string;
  currency?: Currency;
}

export function CategoryBreakdown({
  data,
  title = "Spending by Category",
  description = "Current month",
  currency,
}: CategoryBreakdownProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PieChartIcon className="h-5 w-5 text-muted-foreground" />
          {title}
        </CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="text-sm text-gray-500 py-4 text-center">
            No expenses to break down yet.
          </p>
        ) : (
          <ul className="space-y-3">
            {data.map((row) => {
              const amount = Math.abs(Number(row.total_amount));
              const pct = Math.min(100, Math.max(0, row.percentage));
              const key = row.category_id ?? "uncategorized";
              return (
                <li key={key} className="space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="inline-flex h-7 w-7 items-center justify-center rounded-md shrink-0"
                        style={{ backgroundColor: row.category_color + "20", color: row.category_color }}
                      >
                        <DynamicIcon name={row.category_icon} className="h-4 w-4" />
                      </span>
                      <span className="font-medium truncate">{row.category_name}</span>
                      <span className="text-xs text-gray-500 shrink-0">
                        ({row.transaction_count})
                      </span>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-semibold text-red-600">{formatCurrency(amount, currency)}</div>
                      <div className="text-xs text-gray-500">{pct.toFixed(1)}%</div>
                    </div>
                  </div>
                  <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${pct}%`, backgroundColor: row.category_color }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
