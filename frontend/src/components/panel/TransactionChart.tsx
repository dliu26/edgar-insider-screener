"use client";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { FilingRecord } from "@/types";
import { formatDate } from "@/lib/formatters";

interface Props {
  current: FilingRecord;
  history: FilingRecord[];
}

export function TransactionChart({ current, history }: Props) {
  const allTransactions = [...history, current].sort(
    (a, b) => new Date(a.transactionDate).getTime() - new Date(b.transactionDate).getTime()
  );

  const data = allTransactions.map((f) => ({
    date: formatDate(f.transactionDate),
    shares: f.shares,
    price: f.pricePerShare,
    isCurrent: f.id === current.id,
  }));

  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2535" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={{ stroke: "#1e2535" }}
          />
          <YAxis
            yAxisId="left"
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={{ stroke: "#1e2535" }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={{ stroke: "#1e2535" }}
          />
          <Tooltip
            contentStyle={{ background: "#161b27", border: "1px solid #252d40", borderRadius: 6 }}
            labelStyle={{ color: "#9ca3af" }}
            itemStyle={{ color: "#e5e7eb" }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "#9ca3af" }} />
          <Bar yAxisId="left" dataKey="shares" name="Shares" fill="#22c55e" opacity={0.7} radius={[2, 2, 0, 0]} />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="price"
            name="Price ($)"
            stroke="#fb923c"
            strokeWidth={2}
            dot={{ fill: "#fb923c", r: 3 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
