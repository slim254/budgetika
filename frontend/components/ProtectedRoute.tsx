"use client";

import { useAuthContext } from '@/contexts/AuthProvider';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';

interface ProtectedRouteProps {
    children: React.ReactNode;
}

const ProtectedRoute = (props: ProtectedRouteProps) => {
    const { session, isLoading } = useAuthContext();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        if (!isLoading && !session) {
            router.push('/login?redirect=' + pathname);
        }
    }, [session, isLoading, router, pathname]);

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <p className="text-gray-500">Loading...</p>
            </div>
        );
    }

    if (!session) {
        return null;
    }

    return <>{props.children}</>;
};

export default ProtectedRoute;