import axios from "axios";
import { refreshSession } from "@/services/auth";

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/",
    withCredentials: true,
    timeout: 15000,
});

api.interceptors.request.use((config) => {
    return config;
});

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config || {};
        if (error?.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            try {
                await refreshSession();
                return api(originalRequest);
            } catch {
                return Promise.reject(error);
            }
        }
        return Promise.reject(error);
    }
);

export default api;
