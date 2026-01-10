import { useCallback, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useSleepScoringStore, useMarkers, useDates } from "@/store";
import { fetchWithAuth, getApiBase } from "@/api/client";

// TODO: Generate these types from backend OpenAPI schema
interface FullTableDataPoint {
  timestamp: number;
  datetime_str: string;
  axis_y: number;
  vector_magnitude: number;
  algorithm_result: number | null;
  choi_result: number | null;
  is_nonwear: boolean;
}

interface FullTableResponse {
  data: FullTableDataPoint[];
  total_rows: number;
  start_time: string | null;
  end_time: string | null;
}

interface PopoutTableDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Which marker type to highlight: "onset" or "offset" */
  highlightType?: "onset" | "offset";
}

/**
 * Full 48h data table dialog with click-to-move support.
 * Shows all epochs for the current analysis date.
 */
export function PopoutTableDialog({ open, onOpenChange, highlightType = "onset" }: PopoutTableDialogProps) {
  const currentFileId = useSleepScoringStore((state) => state.currentFileId);
  const { currentDate } = useDates();
  const isAuthenticated = useSleepScoringStore((state) => state.isAuthenticated);

  const { sleepMarkers, selectedPeriodIndex, updateMarker, markerMode } = useMarkers();

  const tableRef = useRef<HTMLDivElement>(null);
  const markerRowRef = useRef<HTMLTableRowElement>(null);

  // Get current marker timestamp for highlighting
  const currentMarker = sleepMarkers[selectedPeriodIndex ?? -1];
  const targetTimestamp = currentMarker
    ? highlightType === "onset" ? currentMarker.onsetTimestamp : currentMarker.offsetTimestamp
    : null;

  // Fetch full table data from API
  const { data: tableData, isLoading } = useQuery({
    queryKey: ["full-table", currentFileId, currentDate],
    queryFn: async () => {
      if (!currentFileId || !currentDate) {
        return null;
      }
      // currentDate is already a string like "2024-01-15"
      const url = `${getApiBase()}/markers/${currentFileId}/${currentDate}/table-full`;
      return fetchWithAuth<FullTableResponse>(url);
    },
    enabled: open && isAuthenticated && !!currentFileId && !!currentDate,
    staleTime: 60000, // Cache for 1 minute
  });

  // Find marker row index
  const markerRowIndex = tableData?.data?.findIndex(
    (row) => targetTimestamp && Math.abs(row.timestamp * 1000 - targetTimestamp) < 60000
  );

  // Scroll marker row into view when data loads
  useEffect(() => {
    if (open && markerRowRef.current && tableRef.current) {
      setTimeout(() => {
        markerRowRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }, 100);
    }
  }, [open, tableData, markerRowIndex]);

  // Handle click-to-move
  const handleRowClick = useCallback((row: FullTableDataPoint) => {
    if (selectedPeriodIndex === null || markerMode !== "sleep") return;

    const newTimestamp = row.timestamp * 1000; // Convert to milliseconds

    if (highlightType === "onset") {
      updateMarker("sleep", selectedPeriodIndex, { onsetTimestamp: newTimestamp });
    } else {
      updateMarker("sleep", selectedPeriodIndex, { offsetTimestamp: newTimestamp });
    }
  }, [selectedPeriodIndex, markerMode, highlightType, updateMarker]);

  const data = tableData?.data ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>
            Full Day Activity Data
          </DialogTitle>
          <DialogDescription>
            {tableData?.start_time && tableData?.end_time && (
              <span>
                {tableData.start_time} to {tableData.end_time} ({tableData.total_rows} epochs)
              </span>
            )}
            {" "}| Click any row to move the {highlightType} marker
          </DialogDescription>
        </DialogHeader>

        <div ref={tableRef} className="flex-1 overflow-auto border rounded-md">
          {isLoading ? (
            <div className="flex items-center justify-center h-32 text-muted-foreground">
              Loading {tableData?.total_rows ?? "..."} rows...
            </div>
          ) : data.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-muted-foreground">
              No data available
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-background border-b z-10">
                <tr>
                  <th className="px-2 py-1.5 text-left whitespace-nowrap font-medium">#</th>
                  <th className="px-2 py-1.5 text-left whitespace-nowrap font-medium">Time</th>
                  <th className="px-2 py-1.5 text-right whitespace-nowrap font-medium" title="Axis Y Activity">Axis Y</th>
                  <th className="px-2 py-1.5 text-right whitespace-nowrap font-medium" title="Vector Magnitude">VM</th>
                  <th className="px-2 py-1.5 text-center whitespace-nowrap font-medium" title="Sleep/Wake">Sleep</th>
                  <th className="px-2 py-1.5 text-center whitespace-nowrap font-medium" title="Choi Nonwear Detection">Choi</th>
                  <th className="px-2 py-1.5 text-center whitespace-nowrap font-medium" title="Manual Nonwear Marker">NWT</th>
                </tr>
              </thead>
              <tbody>
                {data.map((row, idx) => {
                  const isMarkerRow = idx === markerRowIndex;
                  const sleepWake = row.algorithm_result === 1 ? "Sleep" : row.algorithm_result === 0 ? "Wake" : "-";
                  const choiLabel = row.choi_result === 1 ? "Nonwear" : "-";
                  const nwLabel = row.is_nonwear ? "Nonwear" : "-";

                  return (
                    <tr
                      key={idx}
                      ref={isMarkerRow ? markerRowRef : undefined}
                      onClick={() => handleRowClick(row)}
                      className={`border-b cursor-pointer transition-colors ${
                        isMarkerRow
                          ? "bg-purple-500/30 font-bold border-l-4 border-l-purple-600"
                          : "hover:bg-muted/50"
                      }`}
                    >
                      <td className="px-2 py-1 text-muted-foreground font-mono">
                        {idx + 1}
                      </td>
                      <td className={`px-2 py-1 ${isMarkerRow ? "text-purple-700 dark:text-purple-300" : ""}`}>
                        {row.datetime_str}
                      </td>
                      <td className={`px-2 py-1 text-right font-mono ${isMarkerRow ? "text-purple-700 dark:text-purple-300" : ""}`}>
                        {row.axis_y}
                      </td>
                      <td className="px-2 py-1 text-right font-mono text-muted-foreground">
                        {row.vector_magnitude}
                      </td>
                      <td className={`px-2 py-1 text-center ${
                        sleepWake === "Sleep" ? "text-purple-600 dark:text-purple-400" :
                        sleepWake === "Wake" ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"
                      }`}>
                        {sleepWake}
                      </td>
                      <td className={`px-2 py-1 text-center ${
                        choiLabel === "Nonwear" ? "text-red-600 dark:text-red-400" : "text-muted-foreground"
                      }`}>
                        {choiLabel}
                      </td>
                      <td className={`px-2 py-1 text-center ${
                        nwLabel === "Nonwear" ? "text-orange-600 dark:text-orange-400" : "text-muted-foreground"
                      }`}>
                        {nwLabel}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="text-xs text-muted-foreground text-center pt-2">
          Showing {data.length} epochs | Press Escape to close
        </div>
      </DialogContent>
    </Dialog>
  );
}
