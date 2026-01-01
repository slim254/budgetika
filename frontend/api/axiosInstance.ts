import axios from "axios";

export const axiosInstance = axios.create({
  baseURL: "http://localhost:8000/api/",
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

// Response interceptor: Handle 401 errors with token refresh
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Only handle 401 and not already retried
    if (error.response?.status === 401 && !originalRequest?._retry) {
      originalRequest._retry = true;

      try {
        // Try to refresh the token
        const tokenStr = localStorage.getItem("token");
        if (tokenStr) {
          const token = JSON.parse(tokenStr);
          if (token?.refresh) {
            const response = await fetch("http://localhost:8000/api/token/refresh/", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ refresh: token.refresh }),
            });

            if (response.ok) {
              const newToken = await response.json();
              localStorage.setItem("token", JSON.stringify(newToken));
              // Retry the original request with new token
              originalRequest.headers.Authorization = `Bearer ${newToken.access}`;
              return axiosInstance(originalRequest);
            }
          }
        }
      } catch {
        // Refresh failed, will redirect below
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