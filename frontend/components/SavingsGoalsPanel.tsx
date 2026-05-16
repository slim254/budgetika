import React, { useState } from "react";
import { format, formatDistanceToNow } from "date-fns";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  useSavingsGoals,
  useMonthlySummary,
  useDeleteGoal,
  SavingsGoal,
} from "@/api/savingsGoals";
import { SavingsGoalDialog } from "./SavingsGoalDialog";
import { toast } from "sonner";
import { Pencil, Trash2, Plus } from "lucide-react";

interface SavingsGoalsPanelProps {
  walletId: string;
  walletCurrency: string;
}

export function SavingsGoalsPanel({
  walletId,
  walletCurrency,
}: SavingsGoalsPanelProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingGoal, setEditingGoal] = useState<SavingsGoal | null>(null);

  const { data: goals = [], isLoading: goalsLoading } = useSavingsGoals(walletId);
  const { data: summary } = useMonthlySummary(walletId);
  const deleteGoal = useDeleteGoal(walletId);

  const handleDelete = async (goalId: string) => {
    try {
      await deleteGoal.mutateAsync(goalId);
      toast.success("Goal deleted");
    } catch {
      toast.error("Failed to delete goal");
    }
  };

  const handleEdit = (goal: SavingsGoal) => {
    setEditingGoal(goal);
    setDialogOpen(true);
  };

  const handleOpenDialog = () => {
    setEditingGoal(null);
    setDialogOpen(true);
  };

  if (goalsLoading) {
    return <div className="text-sm text-muted-foreground">Loading goals...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Summary Card */}
      {summary && goals.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Monthly Savings Target</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Need to save</p>
                <p className="text-lg font-semibold">
                  {walletCurrency.toUpperCase()} {summary.total_monthly_needed}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Saved this month</p>
                <p className="text-lg font-semibold">
                  {walletCurrency.toUpperCase()} {summary.actual_savings}
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Progress</span>
                <Badge variant={summary.status === "on_track" ? "default" : "secondary"}>
                  {summary.status === "on_track" ? "On Track" : "Short"}
                </Badge>
              </div>
              <Progress
                value={
                  Math.max(0, Math.min(100, (Number(summary.actual_savings) / Number(summary.total_monthly_needed)) * 100))
                }
              />
              {summary.status === "short" && (
                <p className="text-xs text-muted-foreground">
                  Need {walletCurrency.toUpperCase()} {Math.abs(Number(summary.difference)).toFixed(2)} more
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Goals List */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-base">Goals</CardTitle>
          <Button size="sm" onClick={handleOpenDialog}>
            <Plus className="w-4 h-4 mr-1" />
            Add Goal
          </Button>
        </CardHeader>
        <CardContent>
          {goals.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No savings goals yet. Create one to start tracking.
            </p>
          ) : (
            <div className="space-y-3">
              {goals.map((goal) => (
                <div key={goal.id} className="flex items-start justify-between p-3 border rounded">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="font-medium">{goal.name}</p>
                      <Badge variant={goal.status === "active" ? "default" : "secondary"}>
                        {goal.status.charAt(0).toUpperCase() + goal.status.slice(1)}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">
                      Target: {walletCurrency.toUpperCase()} {goal.target_amount} by{" "}
                      {format(new Date(goal.target_date), "MMM d, yyyy")} (
                      {formatDistanceToNow(new Date(goal.target_date), { addSuffix: true })})
                    </p>
                    <p className="text-sm">
                      Need to save: <span className="font-medium">{walletCurrency.toUpperCase()} {goal.monthly_needed}/month</span>
                    </p>
                  </div>
                  {goal.status === "active" && (
                    <div className="flex gap-2 ml-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleEdit(goal)}
                      >
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(goal.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialog */}
      <SavingsGoalDialog
        walletId={walletId}
        goalToEdit={editingGoal}
        isOpen={dialogOpen}
        onOpenChange={setDialogOpen}
        walletCurrency={walletCurrency}
      />
    </div>
  );
}
