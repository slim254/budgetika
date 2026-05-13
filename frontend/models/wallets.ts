export type Currency = 'usd' | 'eur' | 'gbp' | 'pln';

export interface User {
    id: number;
    username: string;
}

export interface Wallet {
    id: string;
    name: string;
    user: number;
    initial_value: number;
    currency: Currency;
    balance: number;
}

export interface Category {
    id: string;
    name: string;
    icon: string;           // Lucide icon name, e.g., 'shopping-cart'
    color: string;          // Hex color, e.g., '#F97316'
    is_visible: boolean;    // Visibility toggle
    is_archived: boolean;
    transaction_count: number;
}

export interface Tag {
    id: string;
    name: string;
    icon: string;           // Lucide icon name
    color: string;          // Hex color
    is_visible: boolean;    // Visibility toggle
    transaction_count: number;
}

export interface Transaction {
    id: string;
    note: string;
    amount: number;  // Positive for income, negative for expenses
    currency: Currency;
    date: string;
    category: Category | null;
    tags: Tag[];
}

// Form data types for creating/updating
export interface TransactionFormData {
    note: string;
    amount: number;  // Positive for income, negative for expenses
    currency: Currency;
    date: string;
    category: string | null;
    tag_ids: string[];
}

export interface WalletFormData {
    name: string;
    initial_value: number;
    currency: Currency;
}

export interface CategoryFormData {
    name: string;
    icon?: string;
    color?: string;
    is_visible?: boolean;
}

export interface TagFormData {
    name: string;
    icon?: string;
    color?: string;
    is_visible?: boolean;
}

// CSV Import types
export interface CSVParseResponse {
    success: boolean;
    columns: string[];
    sample_rows: Record<string, string>[];
    total_rows: number;
    unique_values: Record<string, string[]>;
    error?: string;
}

export interface CSVColumnMapping {
    amount: string;
    date: string;
    note?: string;
    category?: string;
    tags?: string;
    type?: string;
    currency?: string;
}

export type AmountMode = 'signed' | 'type_column' | 'always_expense' | 'always_income';

export interface AmountConfig {
    mode: AmountMode;
    income_value?: string;
    expense_value?: string;
}

export type FilterOperator = 'equals' | 'not_equals' | 'contains' | 'not_contains';

export interface FilterRule {
    column: string;
    operator: FilterOperator;
    value: string;
}

export interface CSVExecuteResponse {
    success: boolean;
    stats: {
        total_rows: number;
        imported: number;
        skipped_filtered: number;
        skipped_duplicates: number;
        errors: number;
    };
    created_categories: string[];
    created_tags: string[];
    errors: Array<{ row: number; error: string }>;
    error?: string;
}

// Dashboard / metrics types — numeric fields are strings because DRF
// DecimalField serializes to JSON strings. Coerce with Number() at render.

export interface DashboardSummary {
    total_balance: string;
    total_income_this_month: string;
    total_expenses_this_month: string;
    net_this_month: string;
}

export interface WalletSummary {
    id: string;
    name: string;
    currency: Currency;
    balance: string;
    income_this_month: string;
    expenses_this_month: string;
}

export interface CategorySpending {
    category_id: string | null;
    category_name: string;
    category_icon: string;
    category_color: string;
    total_amount: string;
    transaction_count: number;
    percentage: number;
}

export interface MonthlyTrendPoint {
    month: string;       // "YYYY-MM"
    income: string;
    expenses: string;
    net: string;
}

export interface UserDashboardResponse {
    summary: DashboardSummary;
    wallets: WalletSummary[];
    spending_by_category: CategorySpending[];
    monthly_trend: MonthlyTrendPoint[];
}

export interface WalletMetricsBlock {
    total_transactions: number;
    income_count: number;
    expense_count: number;
    income_this_month: string;
    expenses_this_month: string;
    net_this_month: string;
    average_transaction: string;
    largest_expense: string;
    largest_income: string;
}

export interface WalletMetricsResponse {
    wallet_id: string;
    wallet_name: string;
    currency: Currency;
    balance: string;
    metrics: WalletMetricsBlock;
    category_breakdown: CategorySpending[];
    recent_transactions: Transaction[];
}

export type RecurringFrequency =
    | "daily"
    | "weekly"
    | "biweekly"
    | "monthly"
    | "quarterly"
    | "yearly";

export interface RecurringTransaction {
    id: string;
    wallet: string;
    note: string;
    amount: number;
    currency: Currency;
    category: Category | null;
    tags: Tag[];
    frequency: RecurringFrequency;
    start_date: string;
    end_date: string | null;
    day_of_week: number | null;
    day_of_month: number | null;
    is_active: boolean;
    next_occurrence: string | null;
    last_processed: string | null;
    execution_count: number;
    is_due: boolean;
    created_at: string;
    updated_at: string;
}

export interface RecurringTransactionFormData {
    note: string;
    amount: number;
    currency: Currency;
    category_id: string | null;
    tag_ids: string[];
    frequency: RecurringFrequency;
    start_date: string;
    end_date: string | null;
    day_of_week: number | null;
    day_of_month: number | null;
    is_active: boolean;
}

export interface RecurringExecution {
    id: string;
    scheduled_date: string;
    executed_at: string;
    transaction: Transaction;
}

export interface SearchFilters {
  category: string;
  tag: string;
  date_from: string;
  date_to: string;
  min_amount: string;
  max_amount: string;
}

export interface TransactionSearchResponse {
  next: string | null;
  previous: string | null;
  results: Transaction[];
}