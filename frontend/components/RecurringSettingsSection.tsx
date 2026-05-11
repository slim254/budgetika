"use client";

import { useEffect, useState } from "react";
import { axiosInstance } from "@/api/axiosInstance";
import { RecurringTransaction, RecurringExecution, RecurringFrequency } from "@/models/wallets";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Edit, Trash2, History } from "lucide-react";
import { formatCurrency } from "@/lib/currency";
import { DynamicIcon } from "@/components/IconPicker";

const FREQUENCY_LABELS: Record<RecurringFrequency, string> = {
  daily: "Daily",
  weekly: "Weekly",
  biweekly: "Every 2 weeks",
  monthly: "Monthly",
  quarterly: "Quarterly",
  yearly: "Yearly",
};

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function frequencyLabel(r: RecurringTransaction): string {
  const base = FREQUENCY_LABELS[r.frequency];
  if (r.frequency === "weekly" && r.day_of_week !== null) {
    return `${base} (${DAY_NAMES[r.day_of_week]})`;
  }
  if (r.frequency === "monthly" && r.day_of_month !== null) {
    const d = r.day_of_month === -1 ? "last day" : `day ${r.day_of_month}`;
    return `${base} (${d})`;
  }
  return base;
}

export function RecurringSettingsSection() {
  const [items, setItems] = useState<RecurringTransaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Edit dialog
  const [editingItem, setEditingItem] = useState<RecurringTransaction | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editFrequency, setEditFrequency] = useState<RecurringFrequency>("monthly");
  const [editDayOfWeek, setEditDayOfWeek] = useState<number>(1);
  const [editDayOfMonth, setEditDayOfMonth] = useState<number>(1);
  const [editEndDate, setEditEndDate] = useState<string>("");
  const [editNote, setEditNote] = useState<string>("");
  const [isSaving, setIsSaving] = useState(false);
  const [editError, setEditError] = useState("");

  // History dialog
  const [historyItem, setHistoryItem] = useState<RecurringTransaction | null>(null);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [executions, setExecutions] = useState<RecurringExecution[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  async function fetchItems() {
    setIsLoading(true);
    try {
      const res = await axiosInstance.get<RecurringTransaction[]>("wallets/recurring/");
      setItems(res.data);
    } catch (err) {
      console.error("Failed to fetch recurring transactions:", err);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    fetchItems();
  }, []);

  async function handleToggleActive(item: RecurringTransaction) {
    try {
      await axiosInstance.patch(`wallets/${item.wallet}/recurring/${item.id}/`, {
        is_active: !item.is_active,
      });
      await fetchItems();
    } catch (err) {
      console.error("Failed to toggle active:", err);
    }
  }

  async function handleDelete(item: RecurringTransaction) {
    if (!confirm(`Delete recurring "${item.note}"? This will not remove already-generated transactions.`)) return;
    try {
      await axiosInstance.delete(`wallets/${item.wallet}/recurring/${item.id}/`);
      await fetchItems();
    } catch (err) {
      console.error("Failed to delete:", err);
    }
  }

  function handleEdit(item: RecurringTransaction) {
    setEditingItem(item);
    setEditFrequency(item.frequency);
    setEditDayOfWeek(item.day_of_week ?? 1);
    setEditDayOfMonth(item.day_of_month ?? 1);
    setEditEndDate(item.end_date ?? "");
    setEditNote(item.note);
    setEditError("");
    setEditDialogOpen(true);
  }

  async function handleSaveEdit() {
    if (!editingItem) return;
    setIsSaving(true);
    setEditError("");
    try {
      await axiosInstance.patch(`wallets/${editingItem.wallet}/recurring/${editingItem.id}/`, {
        note: editNote,
        frequency: editFrequency,
        day_of_week: editFrequency === "weekly" ? editDayOfWeek : null,
        day_of_month: editFrequency === "monthly" ? editDayOfMonth : null,
        end_date: editEndDate || null,
      });
      setEditDialogOpen(false);
      await fetchItems();
    } catch (err) {
      setEditError("Failed to save changes. Please try again.");
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleShowHistory(item: RecurringTransaction) {
    setHistoryItem(item);
    setHistoryDialogOpen(true);
    setIsLoadingHistory(true);
    try {
      const res = await axiosInstance.get<RecurringExecution[]>(
        `wallets/${item.wallet}/recurring/${item.id}/executions/`
      );
      setExecutions(res.data);
    } catch (err) {
      console.error("Failed to fetch executions:", err);
    } finally {
      setIsLoadingHistory(false);
    }
  }

  if (isLoading) {
    return <p className="text-sm text-muted-foreground py-4">Loading recurring transactions...</p>;
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p className="text-sm">No recurring transactions yet.</p>
        <p className="text-xs mt-1">Use the &ldquo;Make this recurring&rdquo; toggle when adding a transaction.</p>
      </div>
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Note</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Frequency</TableHead>
            <TableHead>Next</TableHead>
            <TableHead>Runs</TableHead>
            <TableHead>Active</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const isIncome = Number(item.amount) > 0;
            return (
              <TableRow key={item.id}>
                <TableCell>
                  <div className="font-medium">{item.note}</div>
                  {item.category && (
                    <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                      <div
                        className="w-3 h-3 rounded flex items-center justify-center"
                        style={{ backgroundColor: item.category.color + "20" }}
                      >
                        <DynamicIcon
                          name={item.category.icon || "circle"}
                          className="h-2 w-2"
                          style={{ color: item.category.color }}
                        />
                      </div>
                      {item.category.name}
                    </div>
                  )}
                </TableCell>
                <TableCell className={`font-semibold ${isIncome ? "text-green-600" : "text-red-600"}`}>
                  {isIncome ? "+" : ""}{formatCurrency(item.amount, item.currency)}
                </TableCell>
                <TableCell className="text-sm">{frequencyLabel(item)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {item.next_occurrence ?? "—"}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{item.execution_count}</TableCell>
                <TableCell>
                  <Switch
                    checked={item.is_active}
                    onCheckedChange={() => handleToggleActive(item)}
                  />
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => handleShowHistory(item)} title="View history">
                    <History className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => handleEdit(item)} title="Edit">
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(item)} title="Delete">
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-[450px]">
          <DialogHeader>
            <DialogTitle>Edit Recurring Transaction</DialogTitle>
            <DialogDescription>Update the schedule for this recurring template.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-note">Note</Label>
              <Input
                id="edit-note"
                value={editNote}
                onChange={(e) => setEditNote(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Frequency</Label>
              <Select value={editFrequency} onValueChange={(v) => setEditFrequency(v as RecurringFrequency)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="biweekly">Every 2 weeks</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                  <SelectItem value="quarterly">Quarterly</SelectItem>
                  <SelectItem value="yearly">Yearly</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {editFrequency === "weekly" && (
              <div className="space-y-2">
                <Label>Day of week</Label>
                <Select value={String(editDayOfWeek)} onValueChange={(v) => setEditDayOfWeek(Number(v))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">Monday</SelectItem>
                    <SelectItem value="1">Tuesday</SelectItem>
                    <SelectItem value="2">Wednesday</SelectItem>
                    <SelectItem value="3">Thursday</SelectItem>
                    <SelectItem value="4">Friday</SelectItem>
                    <SelectItem value="5">Saturday</SelectItem>
                    <SelectItem value="6">Sunday</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            {editFrequency === "monthly" && (
              <div className="space-y-2">
                <Label>Day of month</Label>
                <Select value={String(editDayOfMonth)} onValueChange={(v) => setEditDayOfMonth(Number(v))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
                      <SelectItem key={d} value={String(d)}>{d}</SelectItem>
                    ))}
                    <SelectItem value="-1">Last day of month</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="edit-end-date">End date (optional)</Label>
              <Input
                id="edit-end-date"
                type="date"
                value={editEndDate}
                onChange={(e) => setEditEndDate(e.target.value)}
              />
            </div>
            {editError && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">{editError}</div>
            )}
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveEdit} disabled={isSaving}>
              {isSaving ? "Saving..." : "Save"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* History Dialog */}
      <Dialog open={historyDialogOpen} onOpenChange={setHistoryDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Execution History</DialogTitle>
            <DialogDescription>
              {historyItem?.note} — {historyItem && frequencyLabel(historyItem)}
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            {isLoadingHistory ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : executions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No executions yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Scheduled</TableHead>
                    <TableHead>Executed</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {executions.map((ex) => {
                    const isIncome = Number(ex.transaction.amount) > 0;
                    return (
                      <TableRow key={ex.id}>
                        <TableCell className="text-sm">{ex.scheduled_date}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(ex.executed_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell className={`text-right text-sm font-semibold ${isIncome ? "text-green-600" : "text-red-600"}`}>
                          {isIncome ? "+" : ""}{formatCurrency(ex.transaction.amount, ex.transaction.currency)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
