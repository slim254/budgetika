import { axiosInstance } from "./axiosInstance";
import { Transfer, TransferFormData } from "@/models/wallets";

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
