"use client";

import { axiosInstance } from "@/api/axiosInstance";
import ProtectedRoute from "@/components/ProtectedRoute";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, Plus, Edit, Trash2, TrendingUp, TrendingDown, Wallet as WalletIcon, Upload, BarChart3, Search, ArrowLeftRight, Download, Loader2 } from "lucide-react";
import { DynamicIcon } from "@/components/IconPicker";
import { UserMenu } from "@/components/UserMenu";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Wallet, Transaction, Category, Tag, SearchFilters, TransactionSearchResponse } from "@/models/wallets";
import { TransactionDialog } from "@/components/TransactionDialog";
import { CSVImportDialog } from "@/components/CSVImportDialog";
import { WalletTransferDialog } from "@/components/WalletTransferDialog";
import DateSelector from "@/components/DateSelector";
import { formatCurrency } from "@/lib/currency";
import { TransactionSearch } from "@/components/TransactionSearch";
import { BudgetPanel } from "@/components/BudgetPanel";
import { BudgetManagementDialog } from "@/components/BudgetManagementDialog";
import { SavingsGoalsPanel } from "@/components/SavingsGoalsPanel";
import { DeleteWalletDialog } from "@/components/DeleteWalletDialog";
import { WalletDialog } from "@/components/WalletDialog";
import { exportWalletCsv } from "@/api/exports";
import { fetchTransferPeer } from "@/api/transfers";
import { toast } from "sonner";

type TransferEditValues = {
  from_wallet_id: string;
  to_wallet_id: string;
  from_amount: number;
  to_amount: number;
  date: string;
  note: string;
};

export default function WalletPage() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [dialogOpen, setDialogOpen] = useState<boolean>(false);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [keepDialogOpen, setKeepDialogOpen] = useState<boolean>(false);
  const [importDialogOpen, setImportDialogOpen] = useState<boolean>(false);
  const [budgetDialogOpen, setBudgetDialogOpen] = useState(false);
  const [budgetPanelKey, setBudgetPanelKey] = useState(0);
  const [transferDialogOpen, setTransferDialogOpen] = useState(false);
  const [editingTransfer, setEditingTransfer] = useState<Transaction | null>(null);
  const [editTransferValues, setEditTransferValues] = useState<TransferEditValues | null>(null);
  // Id of the transfer row whose peer leg is currently being fetched.
  const [loadingTransferId, setLoadingTransferId] = useState<string | null>(null);
  const [deleteWalletOpen, setDeleteWalletOpen] = useState(false);
  const [editWalletOpen, setEditWalletOpen] = useState(false);

  // Search mode
  const [searchMode, setSearchMode] = useState(false);
  const [searchTransactions, setSearchTransactions] = useState<Transaction[]>([]);
  const [searchCursor, setSearchCursor] = useState<string | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchParamsRef = useRef<{ query: string; filters: SearchFilters }>({
    query: "",
    filters: { category: "", tag: "", date_from: "", date_to: "", min_amount: "", max_amount: "" },
  });
  const sentinelRef = useRef<HTMLDivElement>(null);

  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();

  // Month filtering
  const currentDate = new Date();
  const month = searchParams.get('month') || String(currentDate.getMonth() + 1).padStart(2, '0');
  const year = searchParams.get('year') || String(currentDate.getFullYear());

  // Date range filtering (alternative to month view)
  const dateFrom = searchParams.get('date_from') || '';
  const dateTo = searchParams.get('date_to') || '';
  const isDateRangeMode = Boolean(dateFrom && dateTo);

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

  // Custom date-range mode uses the same unpaginated listing endpoint as month
  // mode (not the cursor-paginated search endpoint), so the summary cards add up
  // over the complete range rather than over the first page.
  async function fetchTransactionsByDateRange(from: string, to: string) {
    try {
      const response = await axiosInstance.get<Transaction[]>(
        `wallets/${params.id}/transactions/?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}`
      );
      setTransactions(response.data);
    } catch (error) {
      console.error("Failed to fetch transactions by date range:", error);
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

  async function fetchWallets() {
    try {
      const response = await axiosInstance.get<Wallet[]>("wallets/");
      setWallets(response.data);
    } catch (error) {
      console.error("Failed to fetch wallets:", error);
    }
  }

  async function loadData(silent = false) {
    if (!silent) setIsLoading(true);
    if (isDateRangeMode) {
      await Promise.all([fetchWallet(), fetchTransactionsByDateRange(dateFrom, dateTo), fetchWallets()]);
    } else {
      await Promise.all([fetchWallet(), fetchTransactions(), fetchWallets()]);
    }
    if (!silent) setIsLoading(false);
  }

  function buildSearchUrl(query: string, filters: SearchFilters, cursor?: string | null): string {
    const p = new URLSearchParams();
    if (query) p.set("search", query);
    if (filters.category) p.set("category", filters.category);
    if (filters.tag) p.set("tag", filters.tag);
    if (filters.date_from) p.set("date_from", filters.date_from);
    if (filters.date_to) p.set("date_to", filters.date_to);
    if (filters.min_amount) p.set("min_amount", filters.min_amount);
    if (filters.max_amount) p.set("max_amount", filters.max_amount);
    if (cursor) p.set("cursor", cursor);
    return `wallets/${params.id}/transactions/search/?${p.toString()}`;
  }

  function extractCursor(nextUrl: string | null): string | null {
    if (!nextUrl) return null;
    try {
      return new URL(nextUrl).searchParams.get("cursor");
    } catch {
      return null;
    }
  }

  async function fetchSearchResults(query: string, filters: SearchFilters) {
    searchParamsRef.current = { query, filters };
    setSearchLoading(true);
    try {
      const response = await axiosInstance.get<TransactionSearchResponse>(
        buildSearchUrl(query, filters)
      );
      setSearchTransactions(response.data.results);
      setSearchCursor(extractCursor(response.data.next));
    } catch (error) {
      console.error("Failed to fetch search results:", error);
    } finally {
      setSearchLoading(false);
    }
  }

  async function loadMoreSearchResults() {
    if (searchLoading || !searchCursor) return;
    setSearchLoading(true);
    try {
      const { query, filters } = searchParamsRef.current;
      const response = await axiosInstance.get<TransactionSearchResponse>(
        buildSearchUrl(query, filters, searchCursor)
      );
      setSearchTransactions((prev) => [...prev, ...response.data.results]);
      setSearchCursor(extractCursor(response.data.next));
    } catch (error) {
      console.error("Failed to load more search results:", error);
    } finally {
      setSearchLoading(false);
    }
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
  }, [params.id, month, year, dateFrom, dateTo, isDateRangeMode]);

  // IntersectionObserver for infinite scroll in search mode
  useEffect(() => {
    if (!searchMode) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMoreSearchResults();
        }
      },
      { threshold: 0.1 }
    );
    if (sentinelRef.current) observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [searchMode, searchCursor]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleDeleteTransaction(transactionId: string) {
    if (!confirm("Are you sure you want to delete this transaction?")) {
      return;
    }
    try {
      await axiosInstance.delete(`transactions/${transactionId}/`);
      toast.success("Transaction deleted");
      if (searchMode) {
        const { query, filters } = searchParamsRef.current;
        await fetchSearchResults(query, filters);
      } else {
        await loadData();
      }
    } catch (error) {
      console.error("Failed to delete transaction:", error);
      alert("Failed to delete transaction. Please try again.");
      toast.error("Failed to delete transaction");
    }
  }

  function handleAddTransfer() {
    setEditingTransfer(null);
    setEditTransferValues(null);
    setTransferDialogOpen(true);
  }

  /**
   * Opens the transfer dialog for an existing transfer.
   *
   * A transfer is two rows: the negative leg is the sending ("from") side, the
   * positive leg is the receiving ("to") side. The clicked row can be either
   * one, and it only knows its own amount — so the peer leg is loaded to get
   * the real other amount instead of mirroring this row's amount, which would
   * rewrite a cross-currency transfer at a 1:1 rate. That fetch is why the row's
   * edit button shows a pending state and rejects re-entry while it is in flight.
   */
  async function handleEditTransfer(transaction: Transaction) {
    if (loadingTransferId) return;

    const peerWallet = transaction.peer_wallet;
    if (!transaction.transfer_ref || !peerWallet) {
      toast.error("This transfer is missing its other side.");
      return;
    }

    setLoadingTransferId(transaction.id);
    try {
      let peer: Transaction | null = null;
      try {
        peer = await fetchTransferPeer(peerWallet.id, transaction.transfer_ref, transaction.date);
      } catch (error) {
        console.error("Failed to load the other side of the transfer:", error);
      }

      const isOutgoing = Number(transaction.amount) < 0;
      let fromAmount: number;
      let toAmount: number;

      if (peer) {
        const outgoingLeg = isOutgoing ? transaction : peer;
        const incomingLeg = isOutgoing ? peer : transaction;
        fromAmount = Math.abs(Number(outgoingLeg.amount));
        toAmount = Math.abs(Number(incomingLeg.amount));
      } else if (peerWallet.currency === wallet?.currency) {
        // Same-currency transfers have equal legs, so the visible row is enough.
        fromAmount = Math.abs(Number(transaction.amount));
        toAmount = fromAmount;
      } else {
        toast.error("Could not load the other side of this transfer.");
        return;
      }

      setEditingTransfer(transaction);
      setEditTransferValues({
        from_wallet_id: isOutgoing ? params.id : peerWallet.id,
        to_wallet_id: isOutgoing ? peerWallet.id : params.id,
        from_amount: fromAmount,
        to_amount: toAmount,
        date: transaction.date,
        note: transaction.note,
      });
      setTransferDialogOpen(true);
    } finally {
      setLoadingTransferId(null);
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
    if (searchMode) {
      const { query, filters } = searchParamsRef.current;
      await fetchSearchResults(query, filters);
    } else {
      await loadData(keepDialogOpen);
    }
  }

  function handleImportDialogClose() {
    setImportDialogOpen(false);
  }

  async function handleImportComplete() {
    toast.success("Import complete");
    await loadData(true);
    fetchCategories();
    fetchTags();
  }

  function handleBudgetChanged() {
    setBudgetPanelKey((k) => k + 1);
  }

  function handleEnterSearchMode() {
    searchParamsRef.current = { query: "", filters: { category: "", tag: "", date_from: "", date_to: "", min_amount: "", max_amount: "" } };
    setSearchMode(true);
    fetchSearchResults("", searchParamsRef.current.filters);
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function handleDateChange(params: { month?: string; year?: string; date_from?: string; date_to?: string }) {
    // The DateSelector component handles URL updates via router.push
    // This callback is for any additional state updates if needed
    // Currently, the page will auto-refetch due to month/year/date_from/date_to in useEffect deps
  }

  function handleExitSearchMode() {
    setSearchMode(false);
    setSearchTransactions([]);
    setSearchCursor(null);
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

  function getDisplayLabel(): string {
    if (isDateRangeMode && dateFrom && dateTo) {
      const from = new Date(dateFrom).toLocaleDateString("default", { month: "short", day: "numeric", year: "numeric" });
      const to = new Date(dateTo).toLocaleDateString("default", { month: "short", day: "numeric", year: "numeric" });
      return `${from} – ${to}`;
    }
    const monthName = new Date(parseInt(year), parseInt(month) - 1).toLocaleString("default", { month: "long", year: "numeric" });
    return monthName;
  }

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
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push(`/wallet/${params.id}/metrics`)}
                >
                  <BarChart3 className="mr-2 h-4 w-4" /> View metrics
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditWalletOpen(true)}
                >
                  <Edit className="mr-2 h-4 w-4" /> Edit Wallet
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                  onClick={() => setDeleteWalletOpen(true)}
                >
                  <Trash2 className="mr-2 h-4 w-4" /> Delete Wallet
                </Button>
                <UserMenu />
              </div>
            </div>
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">{wallet.name}</h1>
                <p className="text-sm text-gray-500">Currency: {wallet.currency.toUpperCase()}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-500">Current Balance</p>
                <p className={`text-3xl font-bold ${Number(wallet.balance) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatCurrency(wallet.balance, wallet.currency)}
                </p>
              </div>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid gap-6 md:grid-cols-4 mb-8">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Initial Value</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatCurrency(wallet.initial_value, wallet.currency)}</div>
                <p className="text-xs text-muted-foreground">Starting balance</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Income</CardTitle>
                <TrendingUp className="h-4 w-4 text-green-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{formatCurrency(incomeTotal, wallet.currency)}</div>
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
                <div className="text-2xl font-bold text-red-600">{formatCurrency(expenseTotal, wallet.currency)}</div>
                <p className="text-xs text-muted-foreground">
                  {transactions.filter(t => Number(t.amount) < 0).length} transactions
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Balance</CardTitle>
                <WalletIcon className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${incomeTotal - expenseTotal >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatCurrency(incomeTotal - expenseTotal, wallet.currency)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {searchMode ? "All transactions" : getDisplayLabel()}
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="mb-6 flex items-center gap-4">
            {searchMode ? (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleExitSearchMode}
                >
                  <ArrowLeft className="mr-2 h-4 w-4" /> Month view
                </Button>
                <TransactionSearch
                  categories={categories}
                  tags={tags}
                  onSearch={fetchSearchResults}
                />
              </>
            ) : (
              <>
                <DateSelector onDateChange={handleDateChange} />
                <Button variant="outline" size="sm" onClick={handleEnterSearchMode}>
                  <Search className="mr-2 h-4 w-4" /> Search all transactions
                </Button>
              </>
            )}
          </div>

          {!searchMode && !isDateRangeMode && (
            <BudgetPanel
              key={budgetPanelKey}
              walletId={params.id}
              month={parseInt(month)}
              year={parseInt(year)}
              currency={wallet.currency}
              onManageClick={() => setBudgetDialogOpen(true)}
            />
          )}

          {!searchMode && !isDateRangeMode && (
            <SavingsGoalsPanel walletId={params.id} walletCurrency={wallet.currency} />
          )}

          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>
                    {searchMode
                      ? "All transactions"
                      : `Transactions for ${getDisplayLabel()}`}
                  </CardTitle>
                  <CardDescription>
                    {searchMode ? "Showing search results across all time" : "Manage your income and expenses"}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={async () => {
                      try {
                        await exportWalletCsv(params.id as string);
                        toast.success("Export downloaded");
                      } catch {
                        toast.error("Export failed");
                      }
                    }}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                  <Button variant="outline" onClick={() => setImportDialogOpen(true)}>
                    <Upload className="mr-2 h-4 w-4" />
                    Import CSV
                  </Button>
                  <Button variant="outline" onClick={handleAddTransfer}>
                    <ArrowLeftRight className="mr-2 h-4 w-4" />
                    Transfer
                  </Button>
                  <Button onClick={handleAddTransaction}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Transaction
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {(() => {
                const displayedTransactions = searchMode ? searchTransactions : transactions;
                if (!searchMode && displayedTransactions.length === 0) {
                  return (
                    <div className="text-center py-12">
                      <p className="text-gray-500 mb-4">No transactions yet</p>
                      <Button onClick={handleAddTransaction}>
                        <Plus className="mr-2 h-4 w-4" />
                        Add Your First Transaction
                      </Button>
                    </div>
                  );
                }
                if (searchMode && displayedTransactions.length === 0 && !searchLoading) {
                  return (
                    <div className="text-center py-12">
                      <p className="text-gray-500">No transactions match your search</p>
                    </div>
                  );
                }
                return (
                  <>
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
                        {displayedTransactions.map((transaction) => {
                          if (transaction.transfer_ref) {
                            const isOutgoing = Number(transaction.amount) < 0;
                            const peerName = transaction.peer_wallet?.name ?? "another wallet";
                            return (
                              <TableRow key={transaction.id} className="bg-blue-50/30">
                                <TableCell className="font-medium">
                                  {new Date(transaction.date).toLocaleDateString()}
                                </TableCell>
                                <TableCell>
                                  <div className="flex items-center gap-2">
                                    <ArrowLeftRight className="h-4 w-4 text-blue-500" />
                                    <span className="text-blue-700">
                                      {isOutgoing ? `→ ${peerName}` : `← ${peerName}`}
                                    </span>
                                  </div>
                                </TableCell>
                                <TableCell><span className="text-gray-400">—</span></TableCell>
                                <TableCell><span className="text-gray-400">—</span></TableCell>
                                <TableCell>
                                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                    transfer
                                  </span>
                                </TableCell>
                                <TableCell
                                  className={`text-right font-semibold ${isOutgoing ? "text-red-600" : "text-green-600"}`}
                                >
                                  {isOutgoing ? "" : "+"}
                                  {formatCurrency(transaction.amount, wallet.currency)}
                                </TableCell>
                                <TableCell className="text-right">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    disabled={loadingTransferId !== null}
                                    onClick={() => handleEditTransfer(transaction)}
                                  >
                                    {loadingTransferId === transaction.id ? (
                                      <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                      <Edit className="h-4 w-4" />
                                    )}
                                  </Button>
                                </TableCell>
                              </TableRow>
                            );
                          }
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
                                          color: tag.color,
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
                                <span
                                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                    isIncome ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                                  }`}
                                >
                                  {isIncome ? "income" : "expense"}
                                </span>
                              </TableCell>
                              <TableCell
                                className={`text-right font-semibold ${
                                  isIncome ? "text-green-600" : "text-red-600"
                                }`}
                              >
                                {isIncome ? "+" : ""}
                                {formatCurrency(transaction.amount, wallet.currency)}
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

                    {/* Infinite scroll sentinel (search mode only) */}
                    {searchMode && (
                      <div ref={sentinelRef} className="py-4 text-center text-sm text-gray-400">
                        {searchLoading && "Loading more..."}
                        {!searchLoading && !searchCursor && searchTransactions.length > 0 && "No more transactions"}
                      </div>
                    )}
                  </>
                );
              })()}
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

      <CSVImportDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        onClose={handleImportDialogClose}
        onImported={handleImportComplete}
        walletId={params.id}
      />

      <BudgetManagementDialog
        open={budgetDialogOpen}
        onOpenChange={setBudgetDialogOpen}
        walletId={params.id}
        month={parseInt(month)}
        year={parseInt(year)}
        categories={categories}
        currency={wallet.currency}
        onChanged={handleBudgetChanged}
      />

      {wallet && (
        <WalletTransferDialog
          open={transferDialogOpen}
          onOpenChange={setTransferDialogOpen}
          onSaved={loadData}
          onDeleted={loadData}
          wallets={wallets}
          currentWalletId={params.id}
          editTransferRef={editingTransfer?.transfer_ref ?? null}
          editValues={editTransferValues}
        />
      )}
      {wallet && (
        <DeleteWalletDialog
          open={deleteWalletOpen}
          onOpenChange={setDeleteWalletOpen}
          walletId={wallet.id}
          walletName={wallet.name}
          onDeleted={() => router.push("/dashboard")}
        />
      )}
      {wallet && (
        <WalletDialog
          open={editWalletOpen}
          onOpenChange={setEditWalletOpen}
          wallet={wallet}
          onSaved={fetchWallet}
        />
      )}
    </ProtectedRoute>
  );
}
