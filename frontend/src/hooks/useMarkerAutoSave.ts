import { useEffect, useRef, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMarkers, useSleepScoringStore, useDates } from "@/store";
import type { MarkerUpdateRequest, SaveStatusResponse, MarkerType } from "@/api/types";
import { getApiBase } from "@/api/client";

/** Debounce delay in milliseconds */
const SAVE_DEBOUNCE_MS = 1000;

/** Maximum retry attempts */
const MAX_RETRIES = 3;

/**
 * Auto-save hook for markers.
 * Watches for marker changes and debounces save to backend.
 * Implements optimistic updates with retry on failure.
 *
 * Uses generated types from backend OpenAPI schema.
 */
export function useMarkerAutoSave() {
  const currentFileId = useSleepScoringStore((state) => state.currentFileId);
  const { currentDate } = useDates();
  const queryClient = useQueryClient();

  const {
    sleepMarkers,
    nonwearMarkers,
    isDirty,
    setSaving,
    setSaveError,
    markSaved,
  } = useMarkers();

  // Debounce timer ref
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async (data: MarkerUpdateRequest) => {
      const { sitePassword, username } = useSleepScoringStore.getState();
      const response = await fetch(
        `${getApiBase()}/markers/${currentFileId}/${currentDate}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            ...(sitePassword ? { "X-Site-Password": sitePassword } : {}),
            "X-Username": username || "anonymous",
          },
          body: JSON.stringify(data),
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `Save failed: ${response.status}`);
      }

      return response.json() as Promise<SaveStatusResponse>;
    },
    onMutate: () => {
      setSaving(true);
      setSaveError(null);
    },
    onSuccess: () => {
      markSaved();
      retryCountRef.current = 0;
      // Invalidate markers query to refetch updated metrics from backend
      queryClient.invalidateQueries({ queryKey: ["markers", currentFileId, currentDate] });
      // Also invalidate table data since marker positions may have changed
      queryClient.invalidateQueries({ queryKey: ["marker-table"] });
    },
    onError: (error: Error) => {
      setSaving(false);
      setSaveError(error.message);

      // Retry with exponential backoff
      if (retryCountRef.current < MAX_RETRIES) {
        retryCountRef.current += 1;
        const retryDelay = Math.pow(2, retryCountRef.current) * 1000;
        console.warn(
          `Save failed, retrying in ${retryDelay}ms (attempt ${retryCountRef.current}/${MAX_RETRIES})`
        );

        debounceTimerRef.current = setTimeout(() => {
          performSave();
        }, retryDelay);
      }
    },
  });

  // Build save request from current markers (convert store format to API format)
  const buildSaveRequest = useCallback((): MarkerUpdateRequest => {
    // Convert store timestamps (milliseconds) to API timestamps (seconds)
    const convertToSeconds = (ts: number | null): number | null => {
      if (ts === null) return null;
      // If timestamp is greater than year 2100 in ms, it's in milliseconds
      if (ts > 10000000000) {
        return ts / 1000;
      }
      // Already in seconds
      return ts;
    };

    return {
      sleep_markers: sleepMarkers.map((m) => ({
        onset_timestamp: convertToSeconds(m.onsetTimestamp),
        offset_timestamp: convertToSeconds(m.offsetTimestamp),
        marker_index: m.markerIndex,
        marker_type: m.markerType as MarkerType,
      })),
      nonwear_markers: nonwearMarkers.map((m) => ({
        start_timestamp: convertToSeconds(m.startTimestamp),
        end_timestamp: convertToSeconds(m.endTimestamp),
        marker_index: m.markerIndex,
        source: "manual" as const,
      })),
      algorithm_used: null,
      notes: null,
    };
  }, [sleepMarkers, nonwearMarkers]);

  // Perform save
  const performSave = useCallback(() => {
    if (!currentFileId || !currentDate) return;

    const request = buildSaveRequest();
    saveMutation.mutate(request);
  }, [currentFileId, currentDate, buildSaveRequest, saveMutation]);

  // Watch for changes and trigger debounced save
  useEffect(() => {
    // Clear any existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    // Only save if dirty and we have valid context
    if (!isDirty || !currentFileId || !currentDate) {
      return;
    }

    // Reset retry count on new changes
    retryCountRef.current = 0;

    // Start debounce timer
    debounceTimerRef.current = setTimeout(() => {
      performSave();
    }, SAVE_DEBOUNCE_MS);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [isDirty, currentFileId, currentDate, sleepMarkers, nonwearMarkers, performSave]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // Expose manual save for edge cases
  return {
    saveNow: performSave,
    isSaving: saveMutation.isPending,
  };
}
