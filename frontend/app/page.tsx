"use client";

import { useAuthContext } from "@/contexts/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Home() {
  const { session, isLoading } = useAuthContext();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) {
      if (session) {
        router.push("/dashboard");
      } else {
        router.push("/login");
      }
    }
  }, [session, isLoading, router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-gray-500">Loading...</p>
    </div>
  );
}
