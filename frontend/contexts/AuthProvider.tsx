"use client";
import type { JwtPayload } from "jwt-decode";
import { jwtDecode } from "jwt-decode";
import { createContext, useContext, useEffect, useState } from "react";

/**
 * Session object containing user information and JWT tokens.
 *
 * The 'exp' field is the token expiration time as a Unix timestamp in seconds
 * (this is standard in JWT specs). To check if expired: exp * 1000 > Date.now()
 */
interface Session {
    user: { id: number; username: string };
    token: { access: string; refresh: string; exp: number };
}

/**
 * AuthContext value interface defining all authentication-related methods and state.
 *
 * Methods:
 * - login: Takes username and password, calls backend API to get JWT tokens
 * - refreshToken: Takes the refresh token and gets a new access token
 */
interface AuthContextValue {
    session: Session | null;
    login: (email: string, password: string) => Promise<void>;
    refreshToken: () => Promise<void>;
    logout: () => void;
    isLoading: boolean;
}

// Create the context object - holds authentication state and methods
const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
    children: React.ReactNode;
}

/**
 * AuthProvider - Context provider for authentication state management.
 *
 * This component wraps your entire app and provides authentication state to all
 * child components. It handles:
 * 1. Persisting JWT tokens to localStorage
 * 2. Restoring user session on app load
 * 3. Logging users in with username/password
 * 4. Refreshing expired access tokens
 *
 * Usage in app:
 * ```tsx
 * <AuthProvider>
 *   <YourApp />
 * </AuthProvider>
 * ```
 *
 * Then in any component:
 * ```tsx
 * const { session, login } = useAuthContext();
 * ```
 */
export function AuthProvider(props: AuthProviderProps) {
    const [session, setSession] = useState<Session | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);

    /**
     * TODO: Implement proper OAuth-style token refresh flow
     *
     * Current Implementation:
     * - Access tokens are sent with every request via axios interceptor
     * - When a request fails with 401 (expired token), the interceptor calls refreshToken()
     * - If refresh succeeds, the original request is retried
     * - If refresh fails, user is logged out
     *
     * Improvements Needed:
     * 1. Auto-refresh tokens before they expire (currently only manual refresh)
     * 2. Handle race conditions if multiple requests fail simultaneously
     * 3. Implement proper logout cleanup
     * 4. Add error boundaries for auth failures
     */

    /**
     * Effect: Restore user session from localStorage on app load.
     *
     * This runs once when the component mounts. If a valid token exists in
     * localStorage (from a previous login), it's decoded and the session is
     * restored, keeping the user logged in across page refreshes.
     *
     * Security Note: Storing tokens in localStorage has XSS vulnerabilities.
     * For production, consider using httpOnly cookies instead.
     */
    useEffect(() => {
        const maybeToken = localStorage.getItem("token");
        if (maybeToken) {
            try {
                setSession(sessionFactory(JSON.parse(maybeToken)));
            } catch (error) {
                console.error("Failed to restore session:", error);
                localStorage.removeItem("token");
            }
        }
        setIsLoading(false);
    }, []);

    /**
     * Login function - authenticates user with username/password.
     *
     * Flow:
     * 1. Send POST request to backend with username/password
     * 2. Backend returns { access, refresh } tokens
     * 3. Decode the access token to extract user info
     * 4. Save tokens to localStorage and update session state
     * 5. Axios interceptor will now include token in all future requests
     *
     * Args:
     *   username: User's username
     *   password: User's password
     *
     * Errors: Caught but only logged to console. Should be handled in UI.
     */
    async function login(username: string, password: string) {
        try {
            const tokenResponse = await fetch("http://localhost:8000/api/token/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ username, password }),
            });
            const token = await tokenResponse.json();
            setSession(sessionFactory(token));
            localStorage.setItem("token", JSON.stringify(token));
        } catch (error) {
            console.error(error);
            // TODO: Throw error or set error state so UI can show error message
        }
    }

    /**
     * Refresh access token using the refresh token.
     *
     * Flow:
     * 1. Get current refresh token from session state
     * 2. Send POST request to backend with refresh token
     * 3. Backend returns new { access, refresh } tokens
     * 4. Update session state and localStorage with new tokens
     * 5. Axios interceptor will use new access token for subsequent requests
     *
     * Called By: useAxiosInterceptor hook when a request fails with 401 status
     *
     * Note: The refresh token is stringified before sending, which seems odd.
     * It's already a string, so this may be a bug: JSON.stringify(token.refresh)
     * should probably just be token.refresh
     */
    async function refreshToken() {
        const token = session?.token;
        if (!token) {
            console.error("No token to refresh");
            return;
        }
        try {
            const response = await fetch("http://localhost:8000/api/token/refresh/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ refresh: token.refresh }),
            });
            const newToken = await response.json();
            setSession(sessionFactory(newToken));
            localStorage.setItem("token", JSON.stringify(newToken));
        } catch (error) {
            console.error(error);
            // TODO: Call logout() on refresh failure
        }
    }

    /**
     * TODO: Commented out - proactive token refresh implementation.
     *
     * This effect checks if the access token is about to expire (within 5 minutes)
     * and automatically refreshes it. This prevents the user from getting a 401
     * error in the middle of using the app.
     *
     * To enable:
     * 1. Uncomment the entire useEffect block below
     * 2. Fix the refreshToken() function to properly handle the refresh
     * 3. Add error handling for refresh failures
     *
     * Current issues preventing this from working:
     * - The refreshToken() call is not awaited, so the token might not be
     *   updated before it's checked again
     * - No error handling if refresh fails
     * - The interval runs even if user is idle (wastes requests)
     */

    function logout() {
        setSession(null);
        localStorage.removeItem("token");
    }

    return (
        <AuthContext.Provider value={{ session, login, refreshToken, logout, isLoading }}>
            {props.children}
        </AuthContext.Provider>
    );
}

/**
 * Hook to access authentication context in any component.
 *
 * Usage:
 * ```tsx
 * const { session, login, refreshToken } = useAuthContext();
 * ```
 *
 * Must be called from within a component tree wrapped by AuthProvider.
 * Throws an error if used outside of AuthProvider.
 */
export function useAuthContext() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuthContext must be used within the AuthProvider");
    }
    return context;
}

/**
 * Helper function - Creates a Session object from raw JWT tokens.
 *
 * Takes the backend response (which contains access and refresh tokens) and:
 * 1. Decodes the access token (JWT) to extract user info and expiration
 * 2. Builds a Session object with user data and both tokens
 *
 * Args:
 *   token: Object with { access: string, refresh: string } from backend
 *
 * Returns:
 *   Session object ready to be stored in state/localStorage
 *
 * JWT Structure:
 * The access token is a JWT with payload containing:
 * - user_id: The user's ID
 * - username: The user's username
 * - exp: Token expiration time (Unix timestamp in seconds)
 */
function sessionFactory(token: Session["token"]): Session {
    // Decode the JWT access token to extract claims (user info, expiration, etc.)
    const decodedToken = jwtDecode<{ user_id: number; username: string } & JwtPayload>(
        token.access
    );
    return {
        user: { username: decodedToken.username, id: decodedToken.user_id },
        token: {
            access: token.access,
            refresh: token.refresh,
            exp: decodedToken.exp ?? 0, // exp might be undefined, default to 0
        },
    };
}