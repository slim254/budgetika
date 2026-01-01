"use client";

import { useState, useEffect, FormEvent } from "react";
import { axiosInstance } from "@/api/axiosInstance";
import { Transaction, Category, Currency, TransactionFormData } from "@/models/wallets";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

interface TransactionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose: () => void;
  onSaved: () => void;
  transaction: Transaction | null;
  walletId: string;
  categories: Category[];
  currency: Currency;
}

export function TransactionDialog({
  open,
  onOpenChange,
  onClose,
  onSaved,
  transaction,
  walletId,
  categories,
  currency,
}: TransactionDialogProps) {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [keepOpen, setKeepOpen] = useState<boolean>(false);
  // Track type separately since we need to apply it to amount sign
  const [transactionType, setTransactionType] = useState<"income" | "expense">("expense");
  const [formData, setFormData] = useState<TransactionFormData>({
    note: "",
    amount: 0,  // Always stored as positive in form, sign applied on submit
    currency: currency,
    date: new Date().toISOString().split("T")[0],
    category: null,
  });

  useEffect(() => {
    if (transaction) {
      // Determine type from amount sign
      const isIncome = Number(transaction.amount) > 0;
      setTransactionType(isIncome ? "income" : "expense");
      setFormData({
        note: transaction.note,
        amount: Math.abs(Number(transaction.amount)),  // Store absolute value in form
        currency: transaction.currency,
        date: transaction.date.split("T")[0],  // Handle ISO date format
        category: transaction.category?.id || null,
      });
    } else {
      setTransactionType("expense");
      setFormData({
        note: "",
        amount: 0,
        currency: currency,
        date: new Date().toISOString().split("T")[0],
        category: null,
      });
    }
    setError("");
  }, [transaction, currency, open]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      // Apply sign based on transaction type
      const signedAmount = transactionType === "expense"
        ? -Math.abs(formData.amount)
        : Math.abs(formData.amount);

      const payload = {
        note: formData.note,
        amount: signedAmount,
        currency: formData.currency,
        date: formData.date,
        category_id: formData.category,  // Backend expects category_id for write
        wallet: walletId,
      };

      if (transaction) {
        await axiosInstance.put(`transactions/${transaction.id}/`, payload);
        onSaved();
        onClose();
      } else {
        await axiosInstance.post("transactions/", payload);
        onSaved();

        if (keepOpen) {
          // Reset form for next entry, keep dialog open
          setFormData({
            note: "",
            amount: 0,
            currency: currency,
            date: new Date().toISOString().split("T")[0],
            category: formData.category, // Keep category for convenience
          });
          // Don't close - user can continue adding
        } else {
          onClose();
        }
      }
    } catch (err) {
      console.error("Failed to save transaction:", err);
      setError("Failed to save transaction. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {transaction ? "Edit Transaction" : "Add Transaction"}
          </DialogTitle>
          <DialogDescription>
            {transaction
              ? "Update the details of your transaction."
              : "Add a new transaction to your wallet."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="transaction_type">Type</Label>
            <Select
              value={transactionType}
              onValueChange={(value: "income" | "expense") => setTransactionType(value)}
            >
              <SelectTrigger id="transaction_type">
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="income">Income</SelectItem>
                <SelectItem value="expense">Expense</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="amount">Amount</Label>
            <Input
              id="amount"
              name="amount"
              type="number"
              step="0.01"
              min="0"
              placeholder="0.00"
              value={formData.amount || ""}
              onChange={(e) =>
                setFormData({ ...formData, amount: parseFloat(e.target.value) || 0 })
              }
              required
              disabled={isLoading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="date">Date</Label>
            <Input
              id="date"
              name="date"
              type="date"
              value={formData.date}
              onChange={(e) => setFormData({ ...formData, date: e.target.value })}
              required
              disabled={isLoading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="category">Category (Optional)</Label>
            <Select
              value={formData.category || "none"}
              onValueChange={(value) =>
                setFormData({
                  ...formData,
                  category: value === "none" ? null : value,
                })
              }
            >
              <SelectTrigger id="category">
                <SelectValue placeholder="Select category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Uncategorized</SelectItem>
                {categories.map((cat) => (
                  <SelectItem key={cat.id} value={cat.id}>
                    {cat.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="note">Note</Label>
            <Input
              id="note"
              name="note"
              type="text"
              placeholder="e.g., Grocery shopping"
              value={formData.note}
              onChange={(e) => setFormData({ ...formData, note: e.target.value })}
              required
              disabled={isLoading}
            />
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
              {error}
            </div>
          )}

          <div className="flex items-center justify-between pt-4">
            {!transaction && (
              <div className="flex items-center gap-2">
                <Switch
                  id="keep-open"
                  checked={keepOpen}
                  onCheckedChange={setKeepOpen}
                />
                <Label htmlFor="keep-open" className="text-sm text-muted-foreground cursor-pointer">
                  Keep open
                </Label>
              </div>
            )}
            <div className={`flex gap-3 ${transaction ? 'ml-auto' : ''}`}>
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading
                  ? "Saving..."
                  : transaction
                  ? "Update Transaction"
                  : "Add Transaction"}
              </Button>
            </div>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
