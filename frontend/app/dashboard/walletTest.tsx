"use client"

import { axiosInstance } from "@/api/axiosInstance";
import { useAuthContext } from "@/contexts/AuthProvider";
import { useEffect, useState } from "react";

export function Wallets(){
    const {session} = useAuthContext();
    const [wallets, setWallets] = useState([]);

    async function fetchWallets(){
        axiosInstance.get("wallets")
        .then((data) => {
            setWallets(data.data);
        })
        .catch((error) => {
            console.error(error);
        });
    }

    useEffect(() => {
        if(!session){
            return
        }
        fetchWallets();
    }, [session]);

    if(!session){
        return <div>Not logged in</div>
    }
    console.log({wallets});
    return <div>Wallets</div>
}