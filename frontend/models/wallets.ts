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
    icon: string;
    color: string;
    is_archived: boolean;
    transaction_count: number;
}

export interface Transaction {
    id: string;
    note: string;
    amount: number;  // Positive for income, negative for expenses
    currency: Currency;
    date: string;
    category: Category | null;
}

// Form data types for creating/updating
export interface TransactionFormData {
    note: string;
    amount: number;  // Positive for income, negative for expenses
    currency: Currency;
    date: string;
    category: string | null;
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
}