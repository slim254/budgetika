"use client";

import { axiosInstance } from "@/api/axiosInstance";
import ProtectedRoute from "@/components/ProtectedRoute";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, Plus, Edit, Trash2, TrendingUp, TrendingDown } from "lucide-react";
import { DynamicIcon } from "@/components/IconPicker";
import { UserMenu } from "@/components/UserMenu";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Wallet, Transaction, Category, Tag } from "@/models/wallets";
import { TransactionDialog } from "@/components/TransactionDialog";
import MonthSelector from "@/components/MonthSelector";

export default function WalletPage() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [dialogOpen, setDialogOpen] = useState<boolean>(false);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [keepDialogOpen, setKeepDialogOpen] = useState<boolean>(false);
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();

  // Month filtering
  const currentDate = new Date();
  const month = searchParams.get('month') || String(currentDate.getMonth() + 1).padStart(2, '0');
  const year = searchParams.get('year') || String(currentDate.getFullYear());

  async function fetchWallet() {
    try {
      const response = await axiosInstance.get<Wallet>(`wallets/${params.id}/`);
      setWallet(response.data);
    } catch (error) {
      console.error("Failed to fetch wallet:", error);
    }
  }

  async function fetchTransactions() {
    try {
      const response = await axiosInstance.get<Transaction[]>(
        `wallets/${params.id}/transactions/?month=${month}&year=${year}`
      );
      setTransactions(response.data);
    } catch (error) {
      console.error("Failed to fetch transactions:", error);
    }
  }

  async function fetchCategories() {
    try {
      const response = await axiosInstance.get<Category[]>(`wallets/categories/`);
      setCategories(response.data);
    } catch (error) {
      console.error("Failed to fetch categories:", error);
    }
  }

  async function fetchTags() {
    try {
      const response = await axiosInstance.get<Tag[]>(`wallets/tags/`);
      setTags(response.data);
    } catch (error) {
      console.error("Failed to fetch tags:", error);
    }
  }

  async function loadData() {
    setIsLoading(true);
    await Promise.all([fetchWallet(), fetchTransactions()]);
    setIsLoading(false);
  }

  // Fetch categories and tags once on mount (they don't change with month/year)
  useEffect(() => {
    if (params.id) {
      fetchCategories();
      fetchTags();
    }
  }, [params.id]);

  // Fetch wallet and transactions when month/year changes
  useEffect(() => {
    if (params.id) {
      loadData();
    }
  }, [params.id, month, year]);

  async function handleDeleteTransaction(transactionId: string) {
    if (!confirm("Are you sure you want to delete this transaction?")) {
      return;
    }

    try {
      await axiosInstance.delete(`transactions/${transactionId}/`);
      await loadData();
    } catch (error) {
      console.error("Failed to delete transaction:", error);
      alert("Failed to delete transaction. Please try again.");
    }
  }

  function handleEditTransaction(transaction: Transaction) {
    setEditingTransaction(transaction);
    setDialogOpen(true);
  }

  function handleAddTransaction() {
    setEditingTransaction(null);
    setDialogOpen(true);
  }

  function handleDialogClose() {
    setDialogOpen(false);
    setEditingTransaction(null);
    setKeepDialogOpen(false);
  }

  async function handleTransactionSaved() {
    // Only refresh data - dialog controls its own closing
    await loadData();
  }

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <p className="text-gray-500">Loading wallet...</p>
        </div>
      </ProtectedRoute>
    );
  }

  if (!wallet) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <p className="text-gray-500">Wallet not found</p>
        </div>
      </ProtectedRoute>
    );
  }

  // With signed amounts: positive = income, negative = expense
  const incomeTotal = transactions
    .filter(t => Number(t.amount) > 0)
    .reduce((sum, t) => sum + Number(t.amount), 0);

  const expenseTotal = transactions
    .filter(t => Number(t.amount) < 0)
    .reduce((sum, t) => sum + Math.abs(Number(t.amount)), 0);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex justify-between items-center mb-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push("/dashboard")}
              >
                <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
              </Button>
              <UserMenu />
            </div>
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">{wallet.name}</h1>
                <p className="text-sm text-gray-500">Currency: {wallet.currency.toUpperCase()}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-500">Current Balance</p>
                <p className={`text-3xl font-bold ${Number(wallet.balance) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  ${Number(wallet.balance).toFixed(2)}
                </p>
              </div>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid gap-6 md:grid-cols-3 mb-8">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Initial Value</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">${Number(wallet.initial_value).toFixed(2)}</div>
                <p className="text-xs text-muted-foreground">Starting balance</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Income</CardTitle>
                <TrendingUp className="h-4 w-4 text-green-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">${incomeTotal.toFixed(2)}</div>
                <p className="text-xs text-muted-foreground">
                  {transactions.filter(t => Number(t.amount) > 0).length} transactions
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Expenses</CardTitle>
                <TrendingDown className="h-4 w-4 text-red-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">${expenseTotal.toFixed(2)}</div>
                <p className="text-xs text-muted-foreground">
                  {transactions.filter(t => Number(t.amount) < 0).length} transactions
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="mb-6">
            <MonthSelector />
          </div>

          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>
                    Transactions for {new Date(parseInt(year), parseInt(month) - 1).toLocaleString("default", { month: "long", year: "numeric" })}
                  </CardTitle>
                  <CardDescription>
                    Manage your income and expenses
                  </CardDescription>
                </div>
                <Button onClick={handleAddTransaction}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Transaction
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {transactions.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-gray-500 mb-4">No transactions yet</p>
                  <Button onClick={handleAddTransaction}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Your First Transaction
                  </Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Note</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Tags</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactions.map((transaction) => {
                      const isIncome = Number(transaction.amount) > 0;
                      return (
                        <TableRow key={transaction.id}>
                          <TableCell className="font-medium">
                            {new Date(transaction.date).toLocaleDateString()}
                          </TableCell>
                          <TableCell>{transaction.note}</TableCell>
                          <TableCell>
                            {transaction.category ? (
                              <div className="flex items-center gap-2">
                                <div
                                  className="w-6 h-6 rounded flex items-center justify-center"
                                  style={{ backgroundColor: transaction.category.color + "20" }}
                                >
                                  <DynamicIcon
                                    name={transaction.category.icon || "circle"}
                                    className="h-3 w-3"
                                    style={{ color: transaction.category.color }}
                                  />
                                </div>
                                <span>{transaction.category.name}</span>
                              </div>
                            ) : (
                              <span className="text-gray-400">Uncategorized</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {transaction.tags && transaction.tags.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {transaction.tags.map((tag) => (
                                  <span
                                    key={tag.id}
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
                                    style={{
                                      backgroundColor: tag.color + "20",
                                      color: tag.color
                                    }}
                                  >
                                    <DynamicIcon name={tag.icon || "tag"} className="h-3 w-3" />
                                    {tag.name}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              isIncome
                                ? 'bg-green-100 text-green-800'
                                : 'bg-red-100 text-red-800'
                            }`}>
                              {isIncome ? 'income' : 'expense'}
                            </span>
                          </TableCell>
                          <TableCell className={`text-right font-semibold ${
                            isIncome ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {isIncome ? '+' : ''}${Number(transaction.amount).toFixed(2)}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleEditTransaction(transaction)}
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteTransaction(transaction.id)}
                              >
                                <Trash2 className="h-4 w-4 text-red-600" />
                              </Button>
                            </div>
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

      <TransactionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onClose={handleDialogClose}
        onSaved={handleTransactionSaved}
        onCategoriesChanged={fetchCategories}
        onTagsChanged={fetchTags}
        transaction={editingTransaction}
        walletId={params.id}
        categories={categories}
        tags={tags}
        currency={wallet.currency}
        keepOpen={keepDialogOpen}
        onKeepOpenChange={setKeepDialogOpen}
      />
    </ProtectedRoute>
  );
}
