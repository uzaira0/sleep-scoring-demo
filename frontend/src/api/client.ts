import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { useSleepScoringStore } from "@/store";

/**
 * Base API client for Sleep Scoring Web API.
 *
 * Uses openapi-fetch for type-safe API calls.
 * The schema is generated from the backend's OpenAPI spec.
 */
const baseClient = createClient<paths>({
  baseUrl: "",
});

/**
 * Middleware to add auth headers and handle 401 errors
 */
baseClient.use({
  onRequest: ({ request }) => {
    const token = useSleepScoringStore.getState().accessToken;
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
  onResponse: ({ response }) => {
    // Clear auth on 401 Unauthorized (expired/invalid token)
    if (response.status === 401) {
      useSleepScoringStore.getState().clearAuth();
    }
    return response;
  },
});

export const api = baseClient;

/**
 * Helper function to fetch with authentication.
 * Automatically adds Authorization header using token from store.
 */
export async function fetchWithAuth<T>(url: string, options?: RequestInit): Promise<T> {
  const token = useSleepScoringStore.getState().accessToken;

  const response = await fetch(url, {
    ...options,
    headers: {
      ...options?.headers,
      Authorization: token ? `Bearer ${token}` : "",
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
 * Auth-specific API calls (no token required)
 */
export const authApi = {
  async login(username: string, password: string) {
    // OAuth2 password flow requires form data
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Login failed");
    }

    return response.json() as Promise<{
      access_token: string;
      refresh_token: string;
      token_type: string;
    }>;
  },

  async register(email: string, username: string, password: string) {
    const response = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, username, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Registration failed");
    }

    return response.json();
  },

  async refreshToken(refreshToken: string) {
    const response = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      throw new Error("Token refresh failed");
    }

    return response.json() as Promise<{
      access_token: string;
      refresh_token: string;
      token_type: string;
    }>;
  },

  async getMe(token: string) {
    const response = await fetch("/api/v1/auth/me", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error("Failed to get user info");
    }

    return response.json();
  },
};

/**
 * Settings API calls
 */
export const settingsApi = {
  async getSettings() {
    return fetchWithAuth<import("./types").UserSettingsResponse>("/api/v1/settings");
  },

  async updateSettings(data: import("./types").UserSettingsUpdate) {
    const token = useSleepScoringStore.getState().accessToken;
    const response = await fetch("/api/v1/settings", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
    const token = useSleepScoringStore.getState().accessToken;
    const response = await fetch("/api/v1/settings", {
      method: "DELETE",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
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
      `/api/v1/diary/${fileId}/${date}`
    );
  },

  async updateDiaryEntry(
    fileId: number,
    date: string,
    data: import("./types").DiaryEntryCreate
  ) {
    const token = useSleepScoringStore.getState().accessToken;
    const response = await fetch(`/api/v1/diary/${fileId}/${date}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
    const token = useSleepScoringStore.getState().accessToken;
    const response = await fetch(`/api/v1/diary/${fileId}/${date}`, {
      method: "DELETE",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
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
    const token = useSleepScoringStore.getState().accessToken;
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`/api/v1/diary/${fileId}/upload`, {
      method: "POST",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
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
