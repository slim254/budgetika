"use client";

import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SavingsGoal, useCreateGoal, useUpdateGoal } from "@/api/savingsGoals";
import { toast } from "sonner";

interface SavingsGoalDialogProps {
  walletId: string;
  goalToEdit?: SavingsGoal | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  walletCurrency: string;
}

export function SavingsGoalDialog({
  walletId,
  goalToEdit,
  isOpen,
  onOpenChange,
  walletCurrency,
}: SavingsGoalDialogProps) {
  const [name, setName] = useState(goalToEdit?.name || "");
  const [targetAmount, setTargetAmount] = useState(goalToEdit?.target_amount || "");
  const [targetDate, setTargetDate] = useState(goalToEdit?.target_date || "");
  const [isLoading, setIsLoading] = useState(false);

  const createGoal = useCreateGoal(walletId);
  const updateGoal = useUpdateGoal(walletId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      if (goalToEdit) {
        await updateGoal.mutateAsync({
          goalId: goalToEdit.id,
          data: {
            name,
            target_amount: targetAmount,
            target_date: targetDate,
          },
        });
        toast.success("Goal updated");
      } else {
        await createGoal.mutateAsync({
          name,
          target_amount: targetAmount,
          target_date: targetDate,
        });
        toast.success("Goal created");
      }
      onOpenChange(false);
      setName("");
      setTargetAmount("");
      setTargetDate("");
    } catch (error) {
      toast.error("Failed to save goal");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {goalToEdit ? "Edit Goal" : "Create Savings Goal"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="goal-name">Goal Name</Label>
            <Input
              id="goal-name"
              placeholder="e.g., Wedding gift, Car insurance"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="target-amount">Target Amount</Label>
            <div className="flex items-center gap-2">
              <Input
                id="target-amount"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                value={targetAmount}
                onChange={(e) => setTargetAmount(e.target.value)}
                required
              />
              <span className="text-sm text-muted-foreground">
                {walletCurrency.toUpperCase()}
              </span>
            </div>
          </div>
          <div>
            <Label htmlFor="target-date">Target Date</Label>
            <Input
              id="target-date"
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
              required
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isLoading || !name || !targetAmount || !targetDate}
            >
              {isLoading ? "Saving..." : "Save Goal"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
