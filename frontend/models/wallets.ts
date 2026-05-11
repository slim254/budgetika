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