"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import { axiosInstance } from "@/api/axiosInstance";
import { useEffect, useState } from "react";
import { Wallet } from "@/models/wallets";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { useAuthContext } from "@/contexts/AuthProvider";
import { Wallet as WalletIcon, Plus, TrendingUp, TrendingDown } from "lucide-react";
import { UserMenu } from "@/components/UserMenu";

export default function DashboardPage() {
    const { session } = useAuthContext();
    const [wallets, setWallets] = useState<Wallet[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const router = useRouter();

    async function fetchWallets() {
        try {
            setIsLoading(true);
            const response = await axiosInstance.get<Wallet[]>("wallets/");
            setWallets(response.data);
        } catch (error) {
            console.error("Failed to fetch wallets:", error);
        } finally {
            setIsLoading(false);
        }
    }

    useEffect(() => {
        if (session) {
            fetchWallets();
        }
    }, [session]);

    const totalBalance = wallets.reduce((sum, wallet) => sum + Number(wallet.balance), 0);
    const positiveWallets = wallets.filter(w => Number(w.balance) >= 0).length;
    const negativeWallets = wallets.filter(w => Number(w.balance) < 0).length;

    return (
        <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
                <header className="bg-white shadow-sm">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                        <div className="flex justify-between items-center">
                            <div>
                                <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
                                <p className="text-sm text-gray-500">Welcome back, {session?.user.username}</p>
                            </div>
                            <UserMenu />
                        </div>
                    </div>
                </header>

                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div className="grid gap-6 md:grid-cols-3 mb-8">
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Total Balance</CardTitle>
                                <WalletIcon className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className={`text-2xl font-bold ${totalBalance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    ${totalBalance.toFixed(2)}
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    Across {wallets.length} wallet{wallets.length !== 1 ? 's' : ''}
                                </p>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Positive Wallets</CardTitle>
                                <TrendingUp className="h-4 w-4 text-green-600" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">{positiveWallets}</div>
                                <p className="text-xs text-muted-foreground">
                                    Wallets with positive balance
                                </p>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">Negative Wallets</CardTitle>
                                <TrendingDown className="h-4 w-4 text-red-600" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">{negativeWallets}</div>
                                <p className="text-xs text-muted-foreground">
                                    Wallets with negative balance
                                </p>
                            </CardContent>
                        </Card>
                    </div>

                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-semibold">Your Wallets</h2>
                        <Button>
                            <Plus className="mr-2 h-4 w-4" />
                            New Wallet
                        </Button>
                    </div>

                    {isLoading ? (
                        <div className="text-center py-12">
                            <p className="text-gray-500">Loading wallets...</p>
                        </div>
                    ) : wallets.length === 0 ? (
                        <Card>
                            <CardContent className="py-12">
                                <div className="text-center">
                                    <WalletIcon className="mx-auto h-12 w-12 text-gray-400" />
                                    <h3 className="mt-2 text-sm font-medium text-gray-900">No wallets</h3>
                                    <p className="mt-1 text-sm text-gray-500">Get started by creating a new wallet.</p>
                                    <div className="mt-6">
                                        <Button>
                                            <Plus className="mr-2 h-4 w-4" />
                                            Create Wallet
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                            {wallets.map((wallet) => (
                                <Card
                                    key={wallet.id}
                                    className="cursor-pointer hover:shadow-lg transition-shadow"
                                    onClick={() => router.push(`/wallet/${wallet.id}`)}
                                >
                                    <CardHeader>
                                        <CardTitle className="flex items-center justify-between">
                                            <span>{wallet.name}</span>
                                            <WalletIcon className="h-5 w-5 text-gray-400" />
                                        </CardTitle>
                                        <CardDescription>
                                            Currency: {wallet.currency.toUpperCase()}
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-2">
                                            <div className="flex justify-between">
                                                <span className="text-sm text-gray-500">Balance:</span>
                                                <span className={`text-sm font-semibold ${Number(wallet.balance) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                                    ${Number(wallet.balance).toFixed(2)}
                                                </span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-sm text-gray-500">Initial Value:</span>
                                                <span className="text-sm">${Number(wallet.initial_value).toFixed(2)}</span>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </main>
            </div>
        </ProtectedRoute>
    );
}

