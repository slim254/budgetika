"use client";

import { useState, useEffect, useRef } from "react";
import { Wallet, TransferFormData, Currency } from "@/models/wallets";
import { createTransfer, updateTransfer, deleteTransfer } from "@/api/transfers";
import { getExchangeRate } from "@/api/exchangeRates";
import { formatDateForAPI } from "@/lib/dates";
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

interface WalletTransferDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSaved: () => void;
    onDeleted: () => void;
    wallets: Wallet[];
    currentWalletId: string;
    // For edit mode: pass the transfer_ref and pre-filled values.
    // `from_wallet_id`/`to_wallet_id` describe the transfer's real direction —
    // the sending wallet is not necessarily the wallet being viewed, since the
    // edit can be opened from the receiving side.
    editTransferRef?: string | null;
    editValues?: {
        from_wallet_id: string;
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
    const today = formatDateForAPI(new Date());

    const [fromWalletId, setFromWalletId] = useState(currentWalletId);
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
    // Set while an edit is being populated, so the exchange-rate autofill does
    // not immediately overwrite the transfer's stored received amount.
    const skipNextRateFetchRef = useRef(false);

    // In create mode the sending wallet is always the wallet being viewed; in
    // edit mode it comes from the transfer itself (the negative leg).
    const fromWallet = wallets.find((w) => w.id === fromWalletId);
    const otherWallets = wallets.filter((w) => w.id !== fromWalletId);
    const toWallet = wallets.find((w) => w.id === toWalletId);
    const isCrossCurrency = !!toWallet && toWallet.currency !== fromWallet?.currency;

    // Populate the form once per open. Deliberately not keyed on every derived
    // value: re-running on each render would stomp on what the user is typing.
    useEffect(() => {
        if (!open) {
            setConfirmDelete(false);
            setError(null);
            return;
        }
        if (isEdit && editValues) {
            skipNextRateFetchRef.current = true;
            setFromWalletId(editValues.from_wallet_id);
            setToWalletId(editValues.to_wallet_id);
            setFromAmount(String(editValues.from_amount));
            setToAmount(String(editValues.to_amount));
            setDate(editValues.date.slice(0, 10));
            setNote(editValues.note);
        } else {
            skipNextRateFetchRef.current = false;
            setFromWalletId(currentWalletId);
            const selectable = wallets.filter((w) => w.id !== currentWalletId);
            // Only reset toWalletId if not already selected
            if (!toWalletId && selectable.length > 0) {
                setToWalletId(selectable[0].id);
            }
            setFromAmount("");
            setToAmount("");
            setDate(today);
            setNote("");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, editTransferRef]);

    // Auto-fill to_amount via exchange rate with 300ms debounce
    useEffect(() => {
        if (!open || !isCrossCurrency || !fromAmount || !date || !toWallet || !fromWallet) return;
        const amount = parseFloat(fromAmount);
        if (isNaN(amount) || amount <= 0) return;
        if (skipNextRateFetchRef.current) {
            skipNextRateFetchRef.current = false;
            return;
        }

        if (rateTimerRef.current) clearTimeout(rateTimerRef.current);
        rateTimerRef.current = setTimeout(async () => {
            setIsFetchingRate(true);
            setRateError(null);
            try {
                const data = await getExchangeRate(fromWallet.currency as Currency, toWallet.currency as Currency, date);
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
    }, [fromAmount, date, toWalletId, open, isCrossCurrency, toWallet, fromWallet]);

    async function handleSave() {
        if (!toWalletId || !fromAmount || !date) {
            setError("To wallet, amount, and date are required.");
            return;
        }
        const fa = parseFloat(fromAmount);
        // The received-amount field is only shown for cross-currency transfers;
        // otherwise both legs must stay in lockstep with the sent amount (a
        // stale `toAmount` left over from an edit would desync the pair).
        const ta = isCrossCurrency ? parseFloat(toAmount || fromAmount) : fa;
        if (fa <= 0 || ta <= 0) {
            setError("Amounts must be positive.");
            return;
        }

        // Validate and parse date
        const dateObj = new Date(date + "T00:00:00Z");
        if (isNaN(dateObj.getTime())) {
            setError("Invalid date format");
            return;
        }

        setSaving(true);
        setError(null);
        try {
            if (isEdit && editTransferRef) {
                await updateTransfer(editTransferRef, {
                    note,
                    date: dateObj.toISOString(),
                    from_amount: fa,
                    to_amount: ta,
                });
                toast.success("Transfer updated");
            } else {
                const payload: TransferFormData = {
                    from_wallet: fromWalletId,
                    to_wallet: toWalletId,
                    from_amount: fa,
                    to_amount: ta,
                    date: dateObj.toISOString(),
                    note,
                };
                await createTransfer(payload);
                toast.success("Transfer saved");
            }
            onOpenChange(false);
            onSaved();
        } catch (err) {
            const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to save transfer. Please try again.";
            setError(message);
            toast.error("Failed to save transfer");
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete() {
        if (!editTransferRef) return;
        setDeleting(true);
        try {
            await deleteTransfer(editTransferRef);
            toast.success("Transfer deleted");
            onOpenChange(false);
            onDeleted();
        } catch (err) {
            const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to delete transfer.";
            setError(message);
            toast.error("Failed to save transfer");
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
                        <Input value={fromWallet?.name ?? ""} disabled />
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
                        <Label>Amount ({fromWallet?.currency.toUpperCase()})</Label>
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
