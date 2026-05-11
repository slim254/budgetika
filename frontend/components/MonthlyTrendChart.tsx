"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { MonthlyTrendPoint } from "@/models/wallets";
import { LineChart as LineChartIcon } from "lucide-react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

interface MonthlyTrendChartProps {
  data: MonthlyTrendPoint[];
}

const chartConfig = {
  income: { label: "Income", color: "#16A34A" },
  expenses: { label: "Expenses", color: "#DC2626" },
  net: { label: "Net", color: "#2563EB" },
} satisfies ChartConfig;

function formatMonthLabel(month: string): string {
  // "2026-04" → "Apr 2026"
  const [y, m] = month.split("-").map(Number);
  if (!y || !m) return month;
  return new Date(y, m - 1, 1).toLocaleString("default", { month: "short", year: "numeric" });
}

export function MonthlyTrendChart({ data }: MonthlyTrendChartProps) {
  const points = data.map((d) => ({
    month: formatMonthLabel(d.month),
    income: Number(d.income),
    expenses: Number(d.expenses),
    net: Number(d.net),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LineChartIcon className="h-5 w-5 text-muted-foreground" />
          Monthly Trend
        </CardTitle>
        <CardDescription>Last 6 months</CardDescription>
      </CardHeader>
      <CardContent>
        {points.length < 2 ? (
          <p className="text-sm text-gray-500 py-8 text-center">
            Add more transactions to see your trend.
          </p>
        ) : (
          <ChartContainer config={chartConfig} className="h-[260px] w-full">
            <LineChart data={points} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="month" tickLine={false} axisLine={false} tickMargin={8} />
              <YAxis tickLine={false} axisLine={false} tickMargin={8} width={50} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <ChartLegend content={<ChartLegendContent />} />
              <Line
                dataKey="income"
                type="monotone"
                stroke="var(--color-income)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
              <Line
                dataKey="expenses"
                type="monotone"
                stroke="var(--color-expenses)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
              <Line
                dataKey="net"
                type="monotone"
                stroke="var(--color-net)"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={{ r: 3 }}
              />
            </LineChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
