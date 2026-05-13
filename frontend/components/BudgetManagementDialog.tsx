"use client";

import { useCallback, useEffect, useState } from "react";
import { Trash2, Plus } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import {
  BudgetRule,
  BudgetSummaryItem,
  Category,
  Currency,
} from "@/models/wallets";
import {
  getBudgetRules,
  getBudgetSummary,
  createBudgetRule,
  updateBudgetRule,
  deleteBudgetRule,
  upsertBudgetOverride,
  deleteBudgetOverride,
} from "@/api/budgets";
import { DynamicIcon } from "@/components/IconPicker";
import { formatCurrency } from "@/lib/currency";

interface BudgetManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  walletId: string;
  month: number;
  year: number;
  categories: Category[];
  currency: Currency;
  onChanged: () => void;
}

interface RuleFormState {
  category_id: string;
  amount: string;
  start_date: string;
  end_date: string;
}

const EMPTY_RULE_FORM: RuleFormState = {
  category_id: "",
  amount: "",
  start_date: "",
  end_date: "",
};

export function BudgetManagementDialog({
  open,
  onOpenChange,
  walletId,
  month,
  year,
  categories,
  currency,
  onChanged,
}: BudgetManagementDialogProps) {
  const [rules, setRules] = useState<BudgetRule[]>([]);
  const [summary, setSummary] = useState<BudgetSummaryItem[]>([]);
  const [loading, setLoading] = useState(false);

  // Rule form
  const [ruleForm, setRuleForm] = useState<RuleFormState>(EMPTY_RULE_FORM);
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleError, setRuleError] = useState<string | null>(null);
  const [ruleSaving, setRuleSaving] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Override state: category_id → input value (null = not editing)
  const [overrideEditing, setOverrideEditing] = useState<Record<string, string>>({});
  const [overrideSaving, setOverrideSaving] = useState<Record<string, boolean>>({});
  const [overrideError, setOverrideError] = useState<string | null>(null);

  const loadData = useCallback(() => {
    setLoading(true);
    Promise.all([
      getBudgetRules(walletId),
      getBudgetSummary(walletId, month, year),
    ])
      .then(([rulesRes, summaryRes]) => {
        setRules(rulesRes.data);
        setSummary(summaryRes.data);
      })
      .finally(() => setLoading(false));
  }, [walletId, month, year]);

  useEffect(() => {
    if (open) loadData();
  }, [open, loadData]);

  function startAddRule() {
    setEditingRuleId(null);
    setRuleForm(EMPTY_RULE_FORM);
    setRuleError(null);
    setShowRuleForm(true);
  }

  function startEditRule(rule: BudgetRule) {
    setEditingRuleId(rule.id);
    setRuleForm({
      category_id: rule.category.id,
      amount: rule.amount,
      start_date: rule.start_date.slice(0, 7), // "YYYY-MM"
      end_date: rule.end_date ? rule.end_date.slice(0, 7) : "",
    });
    setRuleError(null);
    setShowRuleForm(true);
  }

  async function saveRule() {
    if (!ruleForm.category_id || !ruleForm.amount || !ruleForm.start_date) {
      setRuleError("Category, amount, and start month are required.");
      return;
    }
    setRuleSaving(true);
    setRuleError(null);
    const payload = {
      category_id: ruleForm.category_id,
      amount: ruleForm.amount,
      start_date: `${ruleForm.start_date}-01`,
      end_date: ruleForm.end_date ? `${ruleForm.end_date}-01` : null,
    };
    try {
      if (editingRuleId) {
        await updateBudgetRule(walletId, editingRuleId, payload);
      } else {
        await createBudgetRule(walletId, payload);
      }
      setShowRuleForm(false);
      setRuleForm(EMPTY_RULE_FORM);
      setEditingRuleId(null);
      loadData();
      onChanged();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: unknown } })?.response?.data;
      setRuleError(
        typeof msg === "string" ? msg : "Failed to save rule. Check for overlapping date ranges."
      );
    } finally {
      setRuleSaving(false);
    }
  }

  async function handleDeleteRule(ruleId: string) {
    if (!confirm("Delete this budget rule?")) return;
    setDeleteError(null);
    try {
      await deleteBudgetRule(walletId, ruleId);
      loadData();
      onChanged();
    } catch {
      setDeleteError("Failed to delete rule. Please try again.");
    }
  }

  function startOverrideEdit(item: BudgetSummaryItem) {
    setOverrideEditing((prev) => ({ ...prev, [item.category.id]: item.limit }));
  }

  function cancelOverrideEdit(categoryId: string) {
    setOverrideEditing((prev) => {
      const next = { ...prev };
      delete next[categoryId];
      return next;
    });
  }

  async function saveOverride(item: BudgetSummaryItem) {
    const amount = overrideEditing[item.category.id];
    if (!amount) return;
    setOverrideError(null);
    setOverrideSaving((prev) => ({ ...prev, [item.category.id]: true }));
    try {
      await upsertBudgetOverride(walletId, {
        category_id: item.category.id,
        year,
        month,
        amount,
      });
      cancelOverrideEdit(item.category.id);
      loadData();
      onChanged();
    } catch {
      setOverrideError("Failed to save override. Please try again.");
    } finally {
      setOverrideSaving((prev) => ({ ...prev, [item.category.id]: false }));
    }
  }

  async function removeOverride(item: BudgetSummaryItem) {
    if (!item.override_id) return;
    setOverrideError(null);
    try {
      await deleteBudgetOverride(walletId, item.override_id);
      loadData();
      onChanged();
    } catch {
      setOverrideError("Failed to remove override. Please try again.");
    }
  }

  const monthLabel = new Date(year, month - 1).toLocaleString("default", {
    month: "long",
    year: "numeric",
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Manage Budgets</DialogTitle>
        </DialogHeader>

        {loading ? (
          <p className="text-sm text-gray-500 py-4">Loading...</p>
        ) : (
          <Tabs defaultValue="rules">
            <TabsList className="w-full">
              <TabsTrigger value="rules" className="flex-1">
                Monthly limits
              </TabsTrigger>
              <TabsTrigger value="month" className="flex-1">
                {monthLabel}
              </TabsTrigger>
            </TabsList>

            {/* --- Monthly limits tab --- */}
            <TabsContent value="rules" className="mt-4 space-y-3">
              {rules.length === 0 && !showRuleForm && (
                <p className="text-sm text-gray-500">No budget rules yet.</p>
              )}

              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <div
                      className="w-6 h-6 rounded flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: rule.category.color + "20" }}
                    >
                      <DynamicIcon
                        name={rule.category.icon || "circle"}
                        className="h-3 w-3"
                        style={{ color: rule.category.color }}
                      />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{rule.category.name}</p>
                      <p className="text-xs text-gray-500">
                        {formatCurrency(rule.amount, currency)}/month ·{" "}
                        {rule.start_date.slice(0, 7)}
                        {rule.end_date ? ` → ${rule.end_date.slice(0, 7)}` : " → no end"}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => startEditRule(rule)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteRule(rule.id)}
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                </div>
              ))}

              {showRuleForm && (
                <div className="border rounded p-3 space-y-3 bg-gray-50">
                  <div className="space-y-1">
                    <Label className="text-xs">Category</Label>
                    <Select
                      value={ruleForm.category_id}
                      onValueChange={(v) =>
                        setRuleForm((f) => ({ ...f, category_id: v }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select category" />
                      </SelectTrigger>
                      <SelectContent>
                        {categories
                          .filter((c) => !c.is_archived)
                          .map((c) => (
                            <SelectItem key={c.id} value={c.id}>
                              {c.name}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1">
                    <Label className="text-xs">Monthly limit</Label>
                    <Input
                      type="number"
                      min="0.01"
                      step="0.01"
                      placeholder="300.00"
                      value={ruleForm.amount}
                      onChange={(e) =>
                        setRuleForm((f) => ({ ...f, amount: e.target.value }))
                      }
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-xs">Start month</Label>
                      <Input
                        type="month"
                        value={ruleForm.start_date}
                        onChange={(e) =>
                          setRuleForm((f) => ({ ...f, start_date: e.target.value }))
                        }
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">End month (optional)</Label>
                      <Input
                        type="month"
                        value={ruleForm.end_date}
                        onChange={(e) =>
                          setRuleForm((f) => ({ ...f, end_date: e.target.value }))
                        }
                      />
                    </div>
                  </div>

                  {ruleError && (
                    <p className="text-xs text-red-600">{ruleError}</p>
                  )}

                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setShowRuleForm(false);
                        setEditingRuleId(null);
                        setRuleError(null);
                      }}
                    >
                      Cancel
                    </Button>
                    <Button size="sm" onClick={saveRule} disabled={ruleSaving}>
                      {ruleSaving ? "Saving..." : "Save"}
                    </Button>
                  </div>
                </div>
              )}

              {deleteError && (
                <p className="text-xs text-red-600">{deleteError}</p>
              )}

              {!showRuleForm && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={startAddRule}
                >
                  <Plus className="h-4 w-4 mr-1" /> Add limit
                </Button>
              )}
            </TabsContent>

            {/* --- This month tab --- */}
            <TabsContent value="month" className="mt-4 space-y-3">
              {overrideError && (
                <p className="text-xs text-red-600">{overrideError}</p>
              )}

              {summary.length === 0 && (
                <p className="text-sm text-gray-500">
                  No active budget rules for this month.
                </p>
              )}

              {summary.map((item) => {
                const isEditing = item.category.id in overrideEditing;
                return (
                  <div key={item.category.id} className="border-b last:border-0 pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
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
                        <span className="text-sm font-medium">{item.category.name}</span>
                        {item.is_override && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                            override
                          </span>
                        )}
                      </div>
                      <span className="text-sm text-gray-600">
                        {formatCurrency(item.limit, currency)}/mo
                      </span>
                    </div>

                    {isEditing ? (
                      <div className="mt-2 flex items-center gap-2">
                        <Input
                          type="number"
                          min="0.01"
                          step="0.01"
                          className="h-8 text-sm"
                          value={overrideEditing[item.category.id]}
                          onChange={(e) =>
                            setOverrideEditing((prev) => ({
                              ...prev,
                              [item.category.id]: e.target.value,
                            }))
                          }
                        />
                        <Button
                          size="sm"
                          className="h-8"
                          onClick={() => saveOverride(item)}
                          disabled={overrideSaving[item.category.id]}
                        >
                          Save
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8"
                          onClick={() => cancelOverrideEdit(item.category.id)}
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <div className="mt-1.5 flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => startOverrideEdit(item)}
                        >
                          Override this month
                        </Button>
                        {item.is_override && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs text-gray-500"
                            onClick={() => removeOverride(item)}
                          >
                            Remove override
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}
