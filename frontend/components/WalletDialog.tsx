"use client";

import { useState, useEffect } from "react";
import { axiosInstance } from "@/api/axiosInstance";
import { Wallet, WalletFormData, Currency } from "@/models/wallets";
import { toast } from "sonner";
import {
    Dialog,
    DialogContent,
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

const CURRENCIES: Currency[] = ["usd", "eur", "gbp", "pln"];

interface WalletDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSaved: () => void;
    // When set, the dialog edits this wallet (PATCH) instead of creating one.
    wallet?: Wallet | null;
}

export function WalletDialog({ open, onOpenChange, onSaved, wallet }: WalletDialogProps) {
    const isEdit = !!wallet;
    const [name, setName] = useState("");
    const [initialValue, setInitialValue] = useState("0");
    const [currency, setCurrency] = useState<Currency>("usd");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!open) {
            setError(null);
            return;
        }
        if (wallet) {
            setName(wallet.name);
            setInitialValue(String(wallet.initial_value));
            setCurrency(wallet.currency);
        } else {
            setName("");
            setInitialValue("0");
            setCurrency("usd");
        }
    }, [open, wallet]);

    async function handleSave() {
        if (!name.trim()) {
            setError("Wallet name is required.");
            return;
        }
        const iv = parseFloat(initialValue);
        if (isNaN(iv)) {
            setError("Initial value must be a number.");
            return;
        }

        setSaving(true);
        setError(null);
        try {
            if (isEdit && wallet) {
                const payload: Partial<WalletFormData> = { name: name.trim(), initial_value: iv };
                await axiosInstance.patch(`wallets/${wallet.id}/`, payload);
                toast.success("Wallet updated");
            } else {
                const payload: WalletFormData = { name: name.trim(), initial_value: iv, currency };
                await axiosInstance.post("wallets/", payload);
                toast.success("Wallet created");
            }
            onOpenChange(false);
            onSaved();
        } catch (err) {
            const data = (err as { response?: { data?: Record<string, string[]> } })?.response?.data;
            const msg = data ? Object.values(data).flat().join(" ") : `Failed to ${isEdit ? "update" : "create"} wallet.`;
            setError(msg);
            toast.error("Failed to save wallet");
        } finally {
            setSaving(false);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{isEdit ? "Edit Wallet" : "New Wallet"}</DialogTitle>
                </DialogHeader>

                <div className="grid gap-4 py-2">
                    <div className="grid gap-1">
                        <Label htmlFor="wallet-name">Name</Label>
                        <Input
                            id="wallet-name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g. Main Account"
                        />
                    </div>

                    <div className="grid gap-1">
                        <Label htmlFor="wallet-currency">Currency</Label>
                        <Select value={currency} onValueChange={(v) => setCurrency(v as Currency)} disabled={isEdit}>
                            <SelectTrigger id="wallet-currency">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {CURRENCIES.map((c) => (
                                    <SelectItem key={c} value={c}>
                                        {c.toUpperCase()}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {isEdit && (
                            <p className="text-xs text-muted-foreground">
                                Currency can&apos;t be changed after a wallet is created.
                            </p>
                        )}
                    </div>

                    <div className="grid gap-1">
                        <Label htmlFor="wallet-initial">Initial Value</Label>
                        <Input
                            id="wallet-initial"
                            type="number"
                            step="0.01"
                            value={initialValue}
                            onChange={(e) => setInitialValue(e.target.value)}
                            placeholder="0.00"
                        />
                    </div>

                    {error && <p className="text-sm text-red-500">{error}</p>}
                </div>

                <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={handleSave} disabled={saving}>
                        {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Wallet"}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
