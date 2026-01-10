import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { useSleepScoringStore } from "@/store";

/**
 * Get API base path.
 * Auto-detects from window.location.pathname for deployment behind reverse proxy.
 * E.g., if app is at /sleep-scoring/, API is at /sleep-scoring/api
 */
function getApiBase(): string {
  if (typeof window === "undefined") return "/api";

  // In development, API is at root
  if (window.location.hostname === "localhost") {
    return "/api";
  }

  // In production, derive from path
  // E.g., /sleep-scoring/scoring -> base is /sleep-scoring
  const pathParts = window.location.pathname.split("/").filter(Boolean);
  if (pathParts.length > 0) {
    return `/${pathParts[0]}/api`;
  }
  return "/api";
}

/**
 * Base API client for Sleep Scoring Web API.
 *
 * Uses openapi-fetch for type-safe API calls.
 * The schema is generated from the backend's OpenAPI spec.
 */
const baseClient = createClient<paths>({
  baseUrl: getApiBase(),
});

/**
 * Middleware to add auth headers and handle 401 errors.
 * Uses site password model with X-Site-Password and X-Username headers.
 */
baseClient.use({
  onRequest: ({ request }) => {
    const { sitePassword, username } = useSleepScoringStore.getState();
    if (sitePassword) {
      request.headers.set("X-Site-Password", sitePassword);
    }
    request.headers.set("X-Username", username || "anonymous");
    return request;
  },
  onResponse: ({ response }) => {
    // Clear auth on 401 Unauthorized (invalid password)
    if (response.status === 401) {
      useSleepScoringStore.getState().clearAuth();
    }
    return response;
  },
});

export const api = baseClient;

/**
 * Helper function to fetch with authentication.
 * Automatically adds X-Site-Password and X-Username headers from store.
 */
export async function fetchWithAuth<T>(url: string, options?: RequestInit): Promise<T> {
  const { sitePassword, username } = useSleepScoringStore.getState();

  const response = await fetch(url, {
    ...options,
    headers: {
      ...options?.headers,
      ...(sitePassword ? { "X-Site-Password": sitePassword } : {}),
      "X-Username": username || "anonymous",
    },
  });

  if (!response.ok) {
    if (response.status === 401) {
      useSleepScoringStore.getState().clearAuth();
    }
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Auth-specific API calls
 */
export const authApi = {
  /**
   * Verify site password.
   * Returns session expiration info if valid.
   */
  async verifyPassword(password: string) {
    const response = await fetch(`${getApiBase()}/auth/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Invalid password");
    }

    return response.json() as Promise<{
      valid: boolean;
      session_expire_hours: number;
    }>;
  },

  /**
   * Check if auth is required (site password configured).
   */
  async getAuthStatus() {
    const response = await fetch(`${getApiBase()}/auth/status`);
    if (!response.ok) {
      throw new Error("Failed to get auth status");
    }
    return response.json() as Promise<{
      auth_required: boolean;
      session_expire_hours: number;
    }>;
  },
};

/**
 * Get auth headers for API calls
 */
function getAuthHeaders(): Record<string, string> {
  const { sitePassword, username } = useSleepScoringStore.getState();
  return {
    ...(sitePassword ? { "X-Site-Password": sitePassword } : {}),
    "X-Username": username || "anonymous",
  };
}

/**
 * Settings API calls
 */
export const settingsApi = {
  async getSettings() {
    return fetchWithAuth<import("./types").UserSettingsResponse>(`${getApiBase()}/settings`);
  },

  async updateSettings(data: import("./types").UserSettingsUpdate) {
    const response = await fetch(`${getApiBase()}/settings`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      if (response.status === 401) {
        useSleepScoringStore.getState().clearAuth();
      }
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json() as Promise<import("./types").UserSettingsResponse>;
  },

  async resetSettings() {
    const response = await fetch(`${getApiBase()}/settings`, {
      method: "DELETE",
      headers: getAuthHeaders(),
    });

    if (!response.ok && response.status !== 204) {
      if (response.status === 401) {
        useSleepScoringStore.getState().clearAuth();
      }
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
  },
};

/**
 * Diary API calls
 */
export const diaryApi = {
  async getDiaryEntry(fileId: number, date: string) {
    return fetchWithAuth<import("./types").DiaryEntryResponse | null>(
      `${getApiBase()}/diary/${fileId}/${date}`
    );
  },

  async updateDiaryEntry(
    fileId: number,
    date: string,
    data: import("./types").DiaryEntryCreate
  ) {
    const response = await fetch(`${getApiBase()}/diary/${fileId}/${date}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      if (response.status === 401) {
        useSleepScoringStore.getState().clearAuth();
      }
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json() as Promise<import("./types").DiaryEntryResponse>;
  },

  async deleteDiaryEntry(fileId: number, date: string) {
    const response = await fetch(`${getApiBase()}/diary/${fileId}/${date}`, {
      method: "DELETE",
      headers: getAuthHeaders(),
    });

    if (!response.ok && response.status !== 204) {
      if (response.status === 401) {
        useSleepScoringStore.getState().clearAuth();
      }
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
  },

  async uploadDiaryCsv(fileId: number, file: File) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${getApiBase()}/diary/${fileId}/upload`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: formData,
    });

    if (!response.ok) {
      if (response.status === 401) {
        useSleepScoringStore.getState().clearAuth();
      }
      const error = await response.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json() as Promise<import("./types").DiaryUploadResponse>;
  },
};

// Export getApiBase for use in other modules
export { getApiBase };
