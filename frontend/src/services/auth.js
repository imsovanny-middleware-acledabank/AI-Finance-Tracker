import axios from "axios";

const authClient = axios.create({
    baseURL: "/",
    withCredentials: true,
    timeout: 15000,
});

export async function getCurrentUser() {
    const { data } = await authClient.get("auth/user/");
    return data;
}

export async function refreshSession() {
    const { data } = await authClient.post("auth/refresh/");
    return data;
}

export async function logoutSession() {
    const { data } = await authClient.post("auth/logout/");
    return data;
}
