"use client";

import axios, { AxiosError } from "axios";
import { API_URL } from "../types";

const TOKEN_KEY = "bakke.access_token";

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

function readAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

api.interceptors.request.use((config) => {
  const token = readAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function toApiError(error: unknown): ApiError {
  if (error instanceof AxiosError) {
    const data = error.response?.data as { detail?: unknown; message?: unknown } | undefined;
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : typeof data?.message === "string"
          ? data.message
          : undefined;
    const message = detail || error.message || "Request failed";
    return new ApiError(message, error.response?.status);
  }
  if (error instanceof Error) return new ApiError(error.message);
  return new ApiError("Request failed");
}

api.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(toApiError(error))
);

export function streamUrl(videoId: string): string {
  return `${API_URL}/videos/${videoId}/stream`;
}

export function caseUrl(caseId: string): string {
  return `${API_URL}/cases/${caseId}`;
}
