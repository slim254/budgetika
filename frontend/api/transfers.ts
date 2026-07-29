import { axiosInstance } from "./axiosInstance";
import { Transaction, Transfer, TransferFormData } from "@/models/wallets";
import { formatDateForAPI } from "@/lib/dates";

export async function createTransfer(data: TransferFormData): Promise<Transfer> {
    const response = await axiosInstance.post<Transfer>("wallets/transfers/", data);
    return response.data;
}

export async function updateTransfer(
    transferRef: string,
    data: { note?: string; date?: string; from_amount?: number; to_amount?: number },
): Promise<Transfer> {
    const response = await axiosInstance.patch<Transfer>(`wallets/transfers/${transferRef}/`, data);
    return response.data;
}

export async function deleteTransfer(transferRef: string): Promise<void> {
    await axiosInstance.delete(`wallets/transfers/${transferRef}/`);
}

/**
 * Loads the other leg of a transfer.
 *
 * Transaction rows only carry `peer_wallet` (id/name/currency) — not the peer's
 * amount — so for a cross-currency transfer the received amount has to be read
 * back from the peer wallet. There is no GET on `wallets/transfers/{ref}/`, so
 * we query the peer wallet's (unpaginated) date-range listing and match on
 * `transfer_ref`. The window is widened by a day on each side because the row's
 * `date` is a UTC datetime while the backend filters on the local calendar date.
 *
 * Returns null when the peer cannot be found.
 */
export async function fetchTransferPeer(
    peerWalletId: string,
    transferRef: string,
    date: string,
): Promise<Transaction | null> {
    const day = new Date(date);
    if (isNaN(day.getTime())) return null;

    const from = new Date(day);
    from.setDate(from.getDate() - 1);
    const to = new Date(day);
    to.setDate(to.getDate() + 1);

    const response = await axiosInstance.get<Transaction[]>(
        `wallets/${peerWalletId}/transactions/?date_from=${formatDateForAPI(from)}&date_to=${formatDateForAPI(to)}`,
    );
    return response.data.find((t) => t.transfer_ref === transferRef) ?? null;
}
