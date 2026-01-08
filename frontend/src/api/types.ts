/**
 * Convenient type re-exports from generated OpenAPI schema.
 *
 * Import from here instead of directly from schema.ts for cleaner imports.
 * All types are auto-generated from backend Pydantic models.
 *
 * To regenerate: bun run generate:types
 */

import type { components, paths } from "./schema";

// =============================================================================
// Schema Types (from Pydantic models)
// =============================================================================

/** Sleep period with onset/offset timestamps */
export type SleepPeriod = components["schemas"]["SleepPeriod"];

/** Manual nonwear period with start/end timestamps */
export type ManualNonwearPeriod = components["schemas"]["ManualNonwearPeriod"];

/** Request to update markers for a file/date */
export type MarkerUpdateRequest = components["schemas"]["MarkerUpdateRequest"];

/** Response with markers and their calculated metrics */
export type MarkersWithMetricsResponse = components["schemas"]["MarkersWithMetricsResponse"];

/** Response after saving markers */
export type SaveStatusResponse = components["schemas"]["SaveStatusResponse"];

/** Complete sleep metrics for a single sleep period */
export type SleepMetrics = components["schemas"]["SleepMetrics"];

/** Activity data in columnar format */
export type ActivityDataColumnar = components["schemas"]["ActivityDataColumnar"];

/** Response for activity data endpoint */
export type ActivityDataResponse = components["schemas"]["ActivityDataResponse"];

/** File metadata */
export type FileInfo = components["schemas"]["FileInfo"];

/** File list response */
export type FileListResponse = components["schemas"]["FileListResponse"];

/** File upload response */
export type FileUploadResponse = components["schemas"]["FileUploadResponse"];

/** User info */
export type UserRead = components["schemas"]["UserRead"];

/** User settings response */
export type UserSettingsResponse = components["schemas"]["UserSettingsResponse"];

/** User settings update request */
export type UserSettingsUpdate = components["schemas"]["UserSettingsUpdate"];

/** Diary entry response */
export type DiaryEntryResponse = components["schemas"]["DiaryEntryResponse"];

/** Diary entry create request */
export type DiaryEntryCreate = components["schemas"]["DiaryEntryCreate"];

/** Diary upload response */
export type DiaryUploadResponse = components["schemas"]["DiaryUploadResponse"];

/** JWT token response */
export type Token = components["schemas"]["Token"];

/** Data point for onset/offset tables */
export type OnsetOffsetDataPoint = components["schemas"]["OnsetOffsetDataPoint"];

/** Response with data points around a marker */
export type OnsetOffsetTableResponse = components["schemas"]["OnsetOffsetTableResponse"];

// =============================================================================
// Enums (from Pydantic StrEnums)
// =============================================================================

/** Sleep marker type: MAIN_SLEEP or NAP */
export type MarkerType = components["schemas"]["MarkerType"];

/** Marker category: sleep or nonwear */
export type MarkerCategory = components["schemas"]["MarkerCategory"];

/** Sleep scoring algorithm type */
export type AlgorithmType = components["schemas"]["AlgorithmType"];

/** File processing status */
export type FileStatus = components["schemas"]["FileStatus"];

/** Verification status for annotations */
export type VerificationStatus = components["schemas"]["VerificationStatus"];

/** Nonwear data source type */
export type NonwearDataSource = components["schemas"]["NonwearDataSource"];

// =============================================================================
// API Path Types (for type-safe fetch)
// =============================================================================

export type { paths, components };

// =============================================================================
// Enum Constants (for comparisons and defaults)
// =============================================================================

export const MARKER_TYPES = {
  MAIN_SLEEP: "MAIN_SLEEP" as const,
  NAP: "NAP" as const,
} satisfies Record<string, MarkerType>;

export const MARKER_CATEGORIES = {
  SLEEP: "sleep" as const,
  NONWEAR: "nonwear" as const,
} satisfies Record<string, MarkerCategory>;

export const VERIFICATION_STATUSES = {
  DRAFT: "draft" as const,
  SUBMITTED: "submitted" as const,
  VERIFIED: "verified" as const,
  DISPUTED: "disputed" as const,
  RESOLVED: "resolved" as const,
} satisfies Record<string, VerificationStatus>;

export const FILE_STATUSES = {
  PENDING: "pending" as const,
  PROCESSING: "processing" as const,
  READY: "ready" as const,
  FAILED: "failed" as const,
} satisfies Record<string, FileStatus>;
