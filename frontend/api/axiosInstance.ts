import axios from "axios";

// Configurable so the app works over LAN on the mini PC.
// Set NEXT_PUBLIC_API_URL in frontend/.env.local (must end with a trailing slash).
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100/api/";

export const axiosInstance = axios.create({
  baseURL: API_URL,
});

// Request interceptor: Add auth token to all requests
axiosInstance.interceptors.request.use(
  (config) => {
    const tokenStr = localStorage.getItem("token");
    if (tokenStr) {
      try {
        const token = JSON.parse(tokenStr);
        if (token && token.access) {
          config.headers.Authorization = `Bearer ${token.access}`;
        }
      } catch (error) {
        console.error("Failed to parse token from localStorage:", error);
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Module-level refresh mutex: concurrent 401s share one in-flight refresh
// promise instead of each firing their own /token/refresh/ request.
let refreshPromise: Promise<{ access: string; refresh?: string } | null> | null = null;

function refreshAccessToken(): Promise<{ access: string; refresh?: string } | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const tokenStr = localStorage.getItem("token");
      if (!tokenStr) {
        return null;
      }
      const oldToken = JSON.parse(tokenStr);
      if (!oldToken?.refresh) {
        return null;
      }

      const response = await fetch(`${API_URL}token/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: oldToken.refresh }),
      });

      if (!response.ok) {
        return null;
      }

      const newToken = await response.json();
      // Merge so the refresh token is preserved if the response omits it,
      // or updated if the backend rotates it.
      const merged = { ...oldToken, ...newToken };
      localStorage.setItem("token", JSON.stringify(merged));
      return merged;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

// Response interceptor: Handle 401 errors with token refresh
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Only handle 401 and not already retried
    if (error.response?.status === 401 && !originalRequest?._retry) {
      originalRequest._retry = true;

      const refreshed = await refreshAccessToken();
      if (refreshed) {
        // Retry the original request with new token
        originalRequest.headers.Authorization = `Bearer ${refreshed.access}`;
        return axiosInstance(originalRequest);
      }

      // If we get here, refresh didn't work - clear token and redirect to login
      localStorage.removeItem("token");
      const currentPath = typeof window !== "undefined" ? window.location.pathname : "/";
      window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
      // Return never-resolving promise to prevent error from propagating to components
      return new Promise(() => {});
    }

    return Promise.reject(error);
  }
);