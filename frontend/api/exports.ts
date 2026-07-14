import { axiosInstance } from "@/api/axiosInstance";

export async function exportWalletCsv(
  walletId: string,
  params?: { month: number; year: number },
): Promise<void> {
  const response = await axiosInstance.get(`wallets/${walletId}/export/`, {
    params,
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `wallet_${walletId}_transactions.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
