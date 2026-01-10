import { useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSleepScoringStore, useMarkers, useDates } from "@/store";
import { fetchWithAuth, getApiBase } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Maximize2 } from "lucide-react";
import type { OnsetOffsetDataPoint, OnsetOffsetTableResponse } from "@/api/types";

interface MarkerDataTableProps {
  /** For sleep: "onset" or "offset". For nonwear: maps to "start" or "end" */
  type: "onset" | "offset";
  /** Callback when user wants to open popout table */
  onOpenPopout?: () => void;
}

/**
 * Shows activity data around a marker timestamp with click-to-move support.
 * Displays 6 columns: Time, Axis Y, VM, Sleep Score, Choi, NWT
 * Supports both sleep markers (onset/offset) and nonwear markers (start/end).
 */
export function MarkerDataTable({ type, onOpenPopout }: MarkerDataTableProps) {
  const currentFileId = useSleepScoringStore((state) => state.currentFileId);
  const { currentDate } = useDates();
  const isAuthenticated = useSleepScoringStore((state) => state.isAuthenticated);

  const { sleepMarkers, nonwearMarkers, selectedPeriodIndex, markerMode, updateMarker } = useMarkers();

  const tableRef = useRef<HTMLDivElement>(null);
  const markerRowRef = useRef<HTMLTableRowElement>(null);

  // Determine title based on mode and type
  const title = markerMode === "sleep"
    ? type === "onset" ? "Sleep Onset Data" : "Sleep Offset Data"
    : type === "onset" ? "Nonwear Start Data" : "Nonwear End Data";

  // Get current marker info for display
  const currentMarker = markerMode === "sleep"
    ? sleepMarkers[selectedPeriodIndex ?? -1]
    : nonwearMarkers[selectedPeriodIndex ?? -1];

  const targetTimestamp = currentMarker
    ? markerMode === "sleep"
      ? type === "onset" ? currentMarker.onsetTimestamp : currentMarker.offsetTimestamp
      : type === "onset" ? currentMarker.startTimestamp : currentMarker.endTimestamp
    : null;

  // Fetch table data from API
  const { data: tableData, isLoading } = useQuery({
    queryKey: ["marker-table", currentFileId, currentDate, selectedPeriodIndex, type],
    queryFn: async () => {
      if (!currentFileId || !currentDate || selectedPeriodIndex === null) {
        return null;
      }
      // currentDate is already a string like "2024-01-15"
      const url = `${getApiBase()}/markers/${currentFileId}/${currentDate}/table/${selectedPeriodIndex + 1}?window_minutes=100`;
      return fetchWithAuth<OnsetOffsetTableResponse>(url);
    },
    enabled: isAuthenticated && !!currentFileId && !!currentDate && selectedPeriodIndex !== null,
    staleTime: 30000, // Cache for 30 seconds
  });

  // Get the appropriate data based on type
  const data = type === "onset" ? tableData?.onset_data : tableData?.offset_data;

  // Find the marker row index
  const markerRowIndex = data?.findIndex(
    (row) => targetTimestamp && Math.abs(row.timestamp * 1000 - targetTimestamp) < 60000
  );

  // Scroll marker row into view when data loads
  useEffect(() => {
    if (markerRowRef.current && tableRef.current) {
      markerRowRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [data, markerRowIndex]);

  // Handle click-to-move: update marker timestamp to clicked row
  const handleRowClick = useCallback((row: OnsetOffsetDataPoint) => {
    if (selectedPeriodIndex === null) return;

    const newTimestamp = row.timestamp * 1000; // Convert to milliseconds

    if (markerMode === "sleep") {
      if (type === "onset") {
        updateMarker("sleep", selectedPeriodIndex, { onsetTimestamp: newTimestamp });
      } else {
        updateMarker("sleep", selectedPeriodIndex, { offsetTimestamp: newTimestamp });
      }
    } else {
      if (type === "onset") {
        updateMarker("nonwear", selectedPeriodIndex, { startTimestamp: newTimestamp });
      } else {
        updateMarker("nonwear", selectedPeriodIndex, { endTimestamp: newTimestamp });
      }
    }
  }, [selectedPeriodIndex, markerMode, type, updateMarker]);

  // Colors based on marker mode
  const isSleepMode = markerMode === "sleep";
  const highlightBgClass = isSleepMode ? "bg-purple-500/30" : "bg-orange-500/30";
  const highlightBorderClass = isSleepMode ? "border-l-purple-600" : "border-l-orange-600";
  const highlightTextClass = isSleepMode
    ? "text-purple-700 dark:text-purple-300"
    : "text-orange-700 dark:text-orange-300";
  const titleBgClass = isSleepMode ? "bg-muted/30" : "bg-orange-100 dark:bg-orange-900/30";

  if (selectedPeriodIndex === null) {
    const emptyMessage = markerMode === "sleep"
      ? "Select a sleep marker to view data"
      : "Select a nonwear marker to view data";

    return (
      <div className="h-full flex flex-col">
        <div className={`text-sm font-medium text-center py-2 border-b ${titleBgClass}`}>
          {title}
        </div>
        <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground p-4">
          {emptyMessage}
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="h-full flex flex-col">
        <div className={`text-sm font-medium text-center py-2 border-b ${titleBgClass}`}>
          {title}
        </div>
        <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
          Loading...
        </div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="h-full flex flex-col">
        <div className={`text-sm font-medium text-center py-2 border-b ${titleBgClass}`}>
          {title}
        </div>
        <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground p-4">
          No data available
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className={`text-sm font-medium text-center py-2 border-b ${titleBgClass} flex items-center justify-between px-2`}>
        <span className="flex-1 text-center">{title}</span>
        {onOpenPopout && (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={onOpenPopout}
            title="Open full 48h table"
          >
            <Maximize2 className="h-3 w-3" />
          </Button>
        )}
      </div>
      <div ref={tableRef} className="flex-1 overflow-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-background border-b z-10">
            <tr>
              <th className="px-1 py-1 text-left whitespace-nowrap">Time</th>
              <th className="px-1 py-1 text-right whitespace-nowrap" title="Axis Y Activity">Y</th>
              <th className="px-1 py-1 text-right whitespace-nowrap" title="Vector Magnitude">VM</th>
              <th className="px-1 py-1 text-center whitespace-nowrap" title="Sleep/Wake">S/W</th>
              <th className="px-1 py-1 text-center whitespace-nowrap" title="Choi Nonwear">Choi</th>
              <th className="px-1 py-1 text-center whitespace-nowrap" title="Manual Nonwear">NW</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => {
              const isMarkerRow = idx === markerRowIndex;
              const sleepWake = row.algorithm_result === 1 ? "S" : row.algorithm_result === 0 ? "W" : "-";
              const choiLabel = row.choi_result === 1 ? "NW" : row.choi_result === 0 ? "-" : "-";
              const nwLabel = row.is_nonwear ? "NW" : "-";

              return (
                <tr
                  key={idx}
                  ref={isMarkerRow ? markerRowRef : undefined}
                  onClick={() => handleRowClick(row)}
                  className={`border-b cursor-pointer transition-colors ${
                    isMarkerRow
                      ? `${highlightBgClass} font-bold border-l-4 ${highlightBorderClass}`
                      : "hover:bg-muted/50"
                  }`}
                >
                  <td className={`px-1 py-0.5 ${isMarkerRow ? highlightTextClass : ""}`}>
                    {row.datetime_str}
                  </td>
                  <td className={`px-1 py-0.5 text-right font-mono ${isMarkerRow ? highlightTextClass : ""}`}>
                    {row.axis_y}
                  </td>
                  <td className={`px-1 py-0.5 text-right font-mono text-muted-foreground`}>
                    {row.vector_magnitude}
                  </td>
                  <td className={`px-1 py-0.5 text-center ${
                    sleepWake === "S" ? "text-purple-600 dark:text-purple-400" :
                    sleepWake === "W" ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"
                  }`}>
                    {sleepWake}
                  </td>
                  <td className={`px-1 py-0.5 text-center ${
                    choiLabel === "NW" ? "text-red-600 dark:text-red-400" : "text-muted-foreground"
                  }`}>
                    {choiLabel}
                  </td>
                  <td className={`px-1 py-0.5 text-center ${
                    nwLabel === "NW" ? "text-orange-600 dark:text-orange-400" : "text-muted-foreground"
                  }`}>
                    {nwLabel}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="text-xs text-muted-foreground text-center py-1 border-t">
        {data.length} rows | Click to move marker
      </div>
    </div>
  );
}
