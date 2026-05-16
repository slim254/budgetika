"use client";

import { useState, useEffect, useRef } from "react";
import { Wallet, Transfer, TransferFormData, Currency } from "@/models/wallets";
import { createTransfer, updateTransfer, deleteTransfer } from "@/api/transfers";
import { getExchangeRate } from "@/api/exchangeRates";
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

interface WalletTransferDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSaved: () => void;
    onDeleted: () => void;
    wallets: Wallet[];
    currentWalletId: string;
    // For edit mode: pass the transfer_ref and pre-filled values
    editTransferRef?: string | null;
    editValues?: {
        to_wallet_id: string;
        from_amount: number;
        to_amount: number;
        date: string;
        note: string;
    } | null;
}

export function WalletTransferDialog({
    open,
    onOpenChange,
    onSaved,
    onDeleted,
    wallets,
    currentWalletId,
    editTransferRef,
    editValues,
}: WalletTransferDialogProps) {
    const isEdit = !!editTransferRef;
    const today = new Date().toISOString().slice(0, 10);

    const [toWalletId, setToWalletId] = useState("");
    const [fromAmount, setFromAmount] = useState("");
    const [toAmount, setToAmount] = useState("");
    const [date, setDate] = useState(today);
    const [note, setNote] = useState("");
    const [isFetchingRate, setIsFetchingRate] = useState(false);
    const [rateError, setRateError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const rateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const currentWallet = wallets.find((w) => w.id === currentWalletId);
    const otherWallets = wallets.filter((w) => w.id !== currentWalletId);
    const toWallet = wallets.find((w) => w.id === toWalletId);
    const isCrossCurrency = !!toWallet && toWallet.currency !== currentWallet?.currency;

    // Populate form when opening in edit mode
    useEffect(() => {
        if (!open) {
            setConfirmDelete(false);
            setError(null);
            return;
        }
        if (isEdit && editValues) {
            setToWalletId(editValues.to_wallet_id);
            setFromAmount(String(editValues.from_amount));
            setToAmount(String(editValues.to_amount));
            setDate(editValues.date.slice(0, 10));
            setNote(editValues.note);
        } else {
            setToWalletId(otherWallets[0]?.id ?? "");
            setFromAmount("");
            setToAmount("");
            setDate(today);
            setNote("");
        }
    }, [open, isEdit]);

    // Auto-fill to_amount via exchange rate with 300ms debounce
    useEffect(() => {
        if (!open || !isCrossCurrency || !fromAmount || !date || !toWallet || !currentWallet) return;
        const amount = parseFloat(fromAmount);
        if (isNaN(amount) || amount <= 0) return;

        if (rateTimerRef.current) clearTimeout(rateTimerRef.current);
        rateTimerRef.current = setTimeout(async () => {
            setIsFetchingRate(true);
            setRateError(null);
            try {
                const data = await getExchangeRate(currentWallet.currency as Currency, toWallet.currency as Currency, date);
                const converted = (amount * parseFloat(data.rate)).toFixed(2);
                setToAmount(converted);
            } catch {
                setRateError("Could not fetch exchange rate.");
            } finally {
                setIsFetchingRate(false);
            }
        }, 300);

        return () => {
            if (rateTimerRef.current) clearTimeout(rateTimerRef.current);
        };
    }, [fromAmount, date, toWalletId, open]);

    async function handleSave() {
        if (!toWalletId || !fromAmount || !date) {
            setError("To wallet, amount, and date are required.");
            return;
        }
        const fa = parseFloat(fromAmount);
        const ta = parseFloat(toAmount || fromAmount);
        if (fa <= 0 || ta <= 0) {
            setError("Amounts must be positive.");
            return;
        }
        setSaving(true);
        setError(null);
        try {
            if (isEdit && editTransferRef) {
                await updateTransfer(editTransferRef, {
                    note,
                    date: new Date(date).toISOString(),
                    from_amount: fa,
                    to_amount: ta,
                });
            } else {
                const payload: TransferFormData = {
                    from_wallet: currentWalletId,
                    to_wallet: toWalletId,
                    from_amount: fa,
                    to_amount: ta,
                    date: new Date(date).toISOString(),
                    note,
                };
                await createTransfer(payload);
            }
            onOpenChange(false);
            onSaved();
        } catch {
            setError("Failed to save transfer. Please try again.");
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete() {
        if (!editTransferRef) return;
        setDeleting(true);
        try {
            await deleteTransfer(editTransferRef);
            onOpenChange(false);
            onDeleted();
        } catch {
            setError("Failed to delete transfer.");
        } finally {
            setDeleting(false);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{isEdit ? "Edit Transfer" : "New Transfer"}</DialogTitle>
                </DialogHeader>

                <div className="grid gap-4 py-2">
                    <div className="grid gap-1">
                        <Label>From</Label>
                        <Input value={currentWallet?.name ?? ""} disabled />
                    </div>

                    <div className="grid gap-1">
                        <Label>To wallet</Label>
                        <Select value={toWalletId} onValueChange={setToWalletId} disabled={isEdit}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select wallet" />
                            </SelectTrigger>
                            <SelectContent>
                                {otherWallets.map((w) => (
                                    <SelectItem key={w.id} value={w.id}>
                                        {w.name} ({w.currency.toUpperCase()})
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="grid gap-1">
                        <Label>Amount ({currentWallet?.currency.toUpperCase()})</Label>
                        <Input
                            type="number"
                            min="0"
                            step="0.01"
                            value={fromAmount}
                            onChange={(e) => setFromAmount(e.target.value)}
                            placeholder="0.00"
                        />
                    </div>

                    {isCrossCurrency && (
                        <div className="grid gap-1">
                            <Label>
                                Received amount ({toWallet?.currency.toUpperCase()})
                                {isFetchingRate && <span className="ml-2 text-xs text-gray-400">fetching rate…</span>}
                            </Label>
                            <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={toAmount}
                                onChange={(e) => setToAmount(e.target.value)}
                                placeholder="0.00"
                            />
                            {rateError && <p className="text-xs text-red-500">{rateError}</p>}
                        </div>
                    )}

                    <div className="grid gap-1">
                        <Label>Date</Label>
                        <Input
                            type="date"
                            value={date}
                            onChange={(e) => setDate(e.target.value)}
                        />
                    </div>

                    <div className="grid gap-1">
                        <Label>Note (optional)</Label>
                        <Input
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                            placeholder="e.g. Rent buffer"
                        />
                    </div>

                    {error && <p className="text-sm text-red-500">{error}</p>}
                </div>

                <div className="flex justify-between">
                    {isEdit && !confirmDelete && (
                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setConfirmDelete(true)}
                        >
                            Delete
                        </Button>
                    )}
                    {isEdit && confirmDelete && (
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-red-600">Delete both sides?</span>
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={handleDelete}
                                disabled={deleting}
                            >
                                {deleting ? "Deleting…" : "Confirm"}
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
                                Cancel
                            </Button>
                        </div>
                    )}
                    {!confirmDelete && (
                        <div className="flex gap-2 ml-auto">
                            <Button variant="outline" onClick={() => onOpenChange(false)}>
                                Cancel
                            </Button>
                            <Button onClick={handleSave} disabled={saving}>
                                {saving ? "Saving…" : isEdit ? "Save changes" : "Transfer"}
                            </Button>
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
