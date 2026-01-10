import { useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSleepScoringStore, useMarkers, useDates } from "@/store";
import { getApiBase } from "@/api/client";
import type { MarkersWithMetricsResponse, SleepPeriod, ManualNonwearPeriod } from "@/api/types";

/**
 * Hook to load markers from the API when file/date changes.
 * Converts API response (timestamps in seconds) to store format (timestamps in milliseconds).
 *
 * Uses generated types from backend OpenAPI schema.
 */
export function useMarkerLoad() {
  const currentFileId = useSleepScoringStore((state) => state.currentFileId);
  const sitePassword = useSleepScoringStore((state) => state.sitePassword);
  const username = useSleepScoringStore((state) => state.username);
  const { currentDate } = useDates();
  const { setSleepMarkers, setNonwearMarkers } = useMarkers();

  // Fetch markers from API
  const fetchMarkers = useCallback(async (): Promise<MarkersWithMetricsResponse | null> => {
    if (!currentFileId || !currentDate) {
      return null;
    }

    const response = await fetch(
      `${getApiBase()}/markers/${currentFileId}/${currentDate}`,
      {
        headers: {
          ...(sitePassword ? { "X-Site-Password": sitePassword } : {}),
          "X-Username": username || "anonymous",
        },
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        // No markers found for this file/date - return empty response
        return {
          sleep_markers: [],
          nonwear_markers: [],
          metrics: [],
          algorithm_results: null,
          verification_status: "draft",
          last_modified_at: null,
          is_dirty: false,
        };
      }
      throw new Error(`Failed to load markers: ${response.status}`);
    }

    return response.json() as Promise<MarkersWithMetricsResponse>;
  }, [currentFileId, currentDate, sitePassword, username]);

  // Query for markers
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["markers", currentFileId, currentDate],
    queryFn: fetchMarkers,
    enabled: !!currentFileId && !!currentDate,
    staleTime: 0, // Always refetch when date/file changes
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
  });

  // Update store when data is loaded
  useEffect(() => {
    if (!data) return;

    // Convert API format (timestamps in seconds) to store format (milliseconds)
    // The API stores timestamps as Unix seconds, but the store uses milliseconds
    const convertTimestamp = (ts: number | null | undefined): number | null => {
      if (ts === null || ts === undefined) return null;
      // If timestamp is less than year 2000 in seconds (~946684800000 ms), it's in seconds
      // Timestamps in seconds will be ~1700000000, in ms will be ~1700000000000
      if (ts < 10000000000) {
        // It's in seconds, convert to milliseconds
        return ts * 1000;
      }
      // Already in milliseconds
      return ts;
    };

    // Convert sleep markers from API format to store format
    const sleepMarkers = (data.sleep_markers ?? []).map((m: SleepPeriod) => ({
      onsetTimestamp: convertTimestamp(m.onset_timestamp),
      offsetTimestamp: convertTimestamp(m.offset_timestamp),
      markerIndex: m.marker_index,
      markerType: m.marker_type,
    }));

    // Convert nonwear markers from API format to store format
    const nonwearMarkers = (data.nonwear_markers ?? []).map((m: ManualNonwearPeriod) => ({
      startTimestamp: convertTimestamp(m.start_timestamp),
      endTimestamp: convertTimestamp(m.end_timestamp),
      markerIndex: m.marker_index,
    }));

    // Update store
    setSleepMarkers(sleepMarkers);
    setNonwearMarkers(nonwearMarkers);
  }, [data, setSleepMarkers, setNonwearMarkers]);

  return {
    isLoading,
    error,
    refetch,
    hasMarkers: (data?.sleep_markers?.length ?? 0) > 0 || (data?.nonwear_markers?.length ?? 0) > 0,
    metrics: data?.metrics ?? [],
    verificationStatus: data?.verification_status ?? "draft",
  };
}
