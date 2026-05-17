"use client";

import { useState } from "react";
import { axiosInstance } from "@/api/axiosInstance";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface DeleteWalletDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    walletId: string;
    walletName: string;
    onDeleted: () => void;
}

export function DeleteWalletDialog({
    open,
    onOpenChange,
    walletId,
    walletName,
    onDeleted,
}: DeleteWalletDialogProps) {
    const [deleting, setDeleting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function handleDelete() {
        setDeleting(true);
        setError(null);
        try {
            await axiosInstance.delete(`wallets/${walletId}/`);
            onOpenChange(false);
            onDeleted();
        } catch {
            setError("Failed to delete wallet. Please try again.");
        } finally {
            setDeleting(false);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Delete "{walletName}"?</DialogTitle>
                </DialogHeader>

                <p className="text-sm text-gray-600">
                    This will permanently delete the wallet and all its transactions. This action cannot be undone.
                </p>

                {error && <p className="text-sm text-red-500">{error}</p>}

                <div className="flex justify-end gap-2 pt-2">
                    <Button variant="outline" onClick={() => onOpenChange(false)} disabled={deleting}>
                        Cancel
                    </Button>
                    <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
                        {deleting ? "Deleting…" : "Delete Wallet"}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
