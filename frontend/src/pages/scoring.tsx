import { useEffect, useCallback, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Loader2, Moon, Watch, Trash2, Upload, FileText, BarChart3, Save, X, Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useSleepScoringStore, useMarkers } from "@/store";
import { ActivityPlot } from "@/components/activity-plot";
import { MarkerDataTable } from "@/components/marker-data-table";
import { useKeyboardShortcuts, useMarkerAutoSave, useMarkerLoad } from "@/hooks";
import type { FileInfo, FileListResponse, ActivityDataResponse } from "@/api/types";

const ACTIVITY_SOURCE_OPTIONS = [
  { value: "axis_y", label: "Y-Axis (Vertical)" },
  { value: "axis_x", label: "X-Axis (Lateral)" },
  { value: "axis_z", label: "Z-Axis (Forward)" },
  { value: "vector_magnitude", label: "Vector Magnitude" },
];

const VIEW_MODE_OPTIONS = [
  { value: "24", label: "24h" },
  { value: "48", label: "48h" },
];

// Types are imported from @/api/types (generated from backend OpenAPI schema)

async function fetchWithAuth<T>(url: string, options?: RequestInit): Promise<T> {
  const token = useSleepScoringStore.getState().accessToken;
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options?.headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (response.status === 401) {
    useSleepScoringStore.getState().clearAuth();
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

/** Format timestamp as HH:MM (marker timestamps are in milliseconds) */
function formatTime(timestamp: number | null): string {
  if (timestamp === null) return "--:--";
  // Marker timestamps are already in milliseconds
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC", // Match the stored data (no timezone conversion)
  });
}

/** Calculate duration in hours and minutes (marker timestamps are in milliseconds) */
function formatDuration(start: number | null, end: number | null): string {
  if (start === null || end === null) return "--";
  // Marker timestamps are in milliseconds
  const durationMs = end - start;
  const hours = Math.floor(durationMs / (1000 * 60 * 60));
  const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
  return `${hours}h ${minutes}m`;
}

/**
 * Main scoring page with activity plot and marker controls
 * Includes integrated file selection dropdown
 */
export function ScoringPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Enable keyboard shortcuts
  useKeyboardShortcuts();

  // Enable auto-save for markers
  useMarkerAutoSave();

  // Load markers from database when file/date changes
  const { isLoading: isLoadingMarkers } = useMarkerLoad();

  // Use individual selectors to avoid object recreation
  const currentFileId = useSleepScoringStore((state) => state.currentFileId);
  const currentFilename = useSleepScoringStore((state) => state.currentFilename);
  const currentDateIndex = useSleepScoringStore((state) => state.currentDateIndex);
  const availableDates = useSleepScoringStore((state) => state.availableDates);
  const availableFiles = useSleepScoringStore((state) => state.availableFiles);
  const isLoading = useSleepScoringStore((state) => state.isLoading);
  const preferredDisplayColumn = useSleepScoringStore((state) => state.preferredDisplayColumn);
  const viewModeHours = useSleepScoringStore((state) => state.viewModeHours);
  const setPreferredDisplayColumn = useSleepScoringStore((state) => state.setPreferredDisplayColumn);
  const setViewModeHours = useSleepScoringStore((state) => state.setViewModeHours);

  const currentDate = availableDates[currentDateIndex] ?? null;

  // Get stable action references
  const setAvailableDates = useSleepScoringStore((state) => state.setAvailableDates);
  const setActivityData = useSleepScoringStore((state) => state.setActivityData);
  const setLoading = useSleepScoringStore((state) => state.setLoading);
  const navigateDate = useSleepScoringStore((state) => state.navigateDate);
  const setCurrentFile = useSleepScoringStore((state) => state.setCurrentFile);
  const setAvailableFiles = useSleepScoringStore((state) => state.setAvailableFiles);

  // Marker state
  const {
    sleepMarkers,
    nonwearMarkers,
    markerMode,
    creationMode,
    selectedPeriodIndex,
    isDirty,
    isSaving,
    setMarkerMode,
    setSelectedPeriod,
    deleteMarker,
    cancelMarkerCreation,
  } = useMarkers();

  // Fetch files list
  const { data: filesData, isLoading: filesLoading } = useQuery({
    queryKey: ["files"],
    queryFn: () => fetchWithAuth<FileListResponse>("/api/v1/files"),
  });

  // Update available files when filesData changes
  useEffect(() => {
    if (filesData?.files) {
      setAvailableFiles(
        filesData.files.map((f) => ({
          id: f.id,
          filename: f.filename,
          status: f.status,
          rowCount: f.row_count,
        }))
      );

      // Auto-select first file if none selected
      if (!currentFileId && filesData.files.length > 0) {
        const firstReadyFile = filesData.files.find((f) => f.status === "ready");
        if (firstReadyFile) {
          setCurrentFile(firstReadyFile.id, firstReadyFile.filename);
        }
      }
    }
  }, [filesData, currentFileId, setAvailableFiles, setCurrentFile]);

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const token = useSleepScoringStore.getState().accessToken;
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/v1/files/upload", {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Upload failed");
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["files"] });
      setUploadError(null);
    },
    onError: (error: Error) => {
      setUploadError(error.message);
    },
  });

  // Handle file upload
  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        uploadMutation.mutate(file);
      }
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    },
    [uploadMutation]
  );

  // Handle file selection from dropdown
  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const fileId = parseInt(e.target.value, 10);
      const file = filesData?.files.find((f) => f.id === fileId);
      if (file && file.status === "ready") {
        setCurrentFile(file.id, file.filename);
      }
    },
    [filesData, setCurrentFile]
  );

  // Fetch available dates for the file
  const { data: datesData } = useQuery({
    queryKey: ["dates", currentFileId],
    queryFn: () => fetchWithAuth<string[]>(`/api/v1/files/${currentFileId}/dates`),
    enabled: !!currentFileId,
  });

  // Update store when dates are fetched (only when datesData changes)
  useEffect(() => {
    if (datesData && datesData.length > 0) {
      setAvailableDates(datesData);
    }
  }, [datesData]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch activity data for current date (use Sadeh endpoint for algorithm results)
  const { data: activityData, isLoading: activityLoading } = useQuery({
    queryKey: ["activity", currentFileId, currentDate, viewModeHours],
    queryFn: async () => {
      setLoading(true);
      return fetchWithAuth<ActivityDataResponse>(
        `/api/v1/activity/${currentFileId}/${currentDate}/sadeh?view_hours=${viewModeHours}`
      );
    },
    enabled: !!currentFileId && !!currentDate,
  });

  // Update store when activity data is fetched
  useEffect(() => {
    if (activityData) {
      setActivityData({
        timestamps: activityData.data.timestamps,
        axisX: activityData.data.axis_x,
        axisY: activityData.data.axis_y,
        axisZ: activityData.data.axis_z,
        vectorMagnitude: activityData.data.vector_magnitude,
        algorithmResults: activityData.algorithm_results ?? null,
        viewStart: activityData.view_start,
        viewEnd: activityData.view_end,
      });
    }
  }, [activityData]); // eslint-disable-line react-hooks/exhaustive-deps

  const canGoPrev = currentDateIndex > 0;
  const canGoNext = currentDateIndex < availableDates.length - 1;

  // Build file options for dropdown
  const fileOptions = (filesData?.files ?? [])
    .filter((f) => f.status === "ready")
    .map((f) => ({
      value: String(f.id),
      label: `${f.filename} (${f.row_count?.toLocaleString() ?? 0} rows)`,
      disabled: f.status !== "ready",
    }));

  // Show empty state if no files
  if (!filesLoading && (!filesData?.files || filesData.files.length === 0)) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6">
        <FileText className="h-16 w-16 text-muted-foreground mb-4" />
        <h2 className="text-xl font-semibold mb-2">No files uploaded</h2>
        <p className="text-muted-foreground mb-6 text-center max-w-md">
          Upload a CSV file to get started with sleep scoring
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleFileUpload}
          className="hidden"
        />
        <Button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadMutation.isPending}
        >
          {uploadMutation.isPending ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Upload className="h-4 w-4 mr-2" />
          )}
          Upload CSV
        </Button>
        {uploadError && (
          <p className="mt-4 text-sm text-destructive">{uploadError}</p>
        )}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-none p-4 border-b flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          {/* File selector dropdown */}
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-muted-foreground" />
            <Select
              options={fileOptions}
              value={currentFileId ? String(currentFileId) : ""}
              onChange={handleFileChange}
              className="min-w-[250px]"
              placeholder="Select a file..."
            />
          </div>

          {/* Upload button */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            className="hidden"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
          >
            {uploadMutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Upload className="h-4 w-4 mr-1" />
            )}
            Upload
          </Button>
        </div>

        {/* Activity source and view mode */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <Label className="text-sm">Source:</Label>
            <Select
              options={ACTIVITY_SOURCE_OPTIONS}
              value={preferredDisplayColumn}
              onChange={(e) => setPreferredDisplayColumn(e.target.value as "axis_x" | "axis_y" | "axis_z" | "vector_magnitude")}
              className="w-[160px]"
            />
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-sm">View:</Label>
            <Select
              options={VIEW_MODE_OPTIONS}
              value={String(viewModeHours)}
              onChange={(e) => setViewModeHours(Number(e.target.value) as 24 | 48)}
              className="w-[70px]"
            />
          </div>
        </div>

        {/* Date navigation */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={() => navigateDate(-1)}
            disabled={!canGoPrev || !currentFileId}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="min-w-[140px] text-center">
            <span className="font-medium">
              {currentDate ?? "No date selected"}
            </span>
            {availableDates.length > 0 && (
              <span className="text-xs text-muted-foreground ml-2">
                ({currentDateIndex + 1}/{availableDates.length})
              </span>
            )}
          </div>
          <Button
            variant="outline"
            size="icon"
            onClick={() => navigateDate(1)}
            disabled={!canGoNext || !currentFileId}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Upload error banner */}
      {uploadError && (
        <div className="flex-none p-2 bg-destructive/10 border-b border-destructive/30 text-destructive text-sm text-center">
          {uploadError}
        </div>
      )}

      {/* Control Bar Row */}
      <div className="flex-none px-4 py-2 border-b flex items-center justify-between gap-4 bg-muted/30">
        {/* Left: Mode toggle */}
        <div className="flex items-center gap-2">
          <Label className="text-sm font-medium">Mode:</Label>
          <div className="flex gap-1">
            <Button
              variant={markerMode === "sleep" ? "default" : "outline"}
              size="sm"
              className="h-8"
              onClick={() => setMarkerMode("sleep")}
            >
              <Moon className="h-4 w-4 mr-1" />
              Sleep
            </Button>
            <Button
              variant={markerMode === "nonwear" ? "default" : "outline"}
              size="sm"
              className="h-8"
              onClick={() => setMarkerMode("nonwear")}
            >
              <Watch className="h-4 w-4 mr-1" />
              Nonwear
            </Button>
          </div>

          {/* Creation mode indicator */}
          {creationMode !== "idle" && (
            <div className="px-2 py-1 bg-amber-500/10 border border-amber-500/30 rounded text-sm flex items-center gap-2">
              <span className="text-amber-600 dark:text-amber-400">
                Click plot for {creationMode === "placing_onset" ? "offset" : "onset"}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={cancelMarkerCreation}
              >
                <X className="h-3 w-3 mr-1" />
                Cancel
              </Button>
            </div>
          )}
        </div>

        {/* Center: Sleep times display */}
        <div className="flex items-center gap-4">
          {markerMode === "sleep" && selectedPeriodIndex !== null && sleepMarkers[selectedPeriodIndex] && (
            <>
              <div className="flex items-center gap-2">
                <Label className="text-sm">Onset:</Label>
                <Input
                  type="text"
                  className="w-20 h-8 text-sm text-center"
                  value={formatTime(sleepMarkers[selectedPeriodIndex].onsetTimestamp)}
                  readOnly
                />
              </div>
              <div className="flex items-center gap-2">
                <Label className="text-sm">Offset:</Label>
                <Input
                  type="text"
                  className="w-20 h-8 text-sm text-center"
                  value={formatTime(sleepMarkers[selectedPeriodIndex].offsetTimestamp)}
                  readOnly
                />
              </div>
              <div className="text-sm font-medium">
                Duration: {formatDuration(
                  sleepMarkers[selectedPeriodIndex].onsetTimestamp,
                  sleepMarkers[selectedPeriodIndex].offsetTimestamp
                )}
              </div>
            </>
          )}
        </div>

        {/* Right: Action buttons */}
        <div className="flex items-center gap-2">
          {/* Save status */}
          <span className="text-xs">
            {isSaving ? (
              <span className="text-amber-600 dark:text-amber-400">Saving...</span>
            ) : isDirty ? (
              <span className="text-muted-foreground">Unsaved</span>
            ) : (sleepMarkers.length > 0 || nonwearMarkers.length > 0) ? (
              <span className="text-green-600 dark:text-green-400">Saved</span>
            ) : null}
          </span>

          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={() => {
              // Mark no sleep for this date
              // TODO: Implement mark no sleep functionality
            }}
          >
            <Ban className="h-4 w-4 mr-1" />
            No Sleep
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-8 text-destructive border-destructive/50 hover:bg-destructive/10"
            onClick={() => {
              if (confirm("Clear all markers for this date?")) {
                // Clear all markers
                useSleepScoringStore.getState().setSleepMarkers([]);
                useSleepScoringStore.getState().setNonwearMarkers([]);
              }
            }}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            Clear
          </Button>
        </div>
      </div>

      {/* Main content - horizontal split with data tables */}
      <div className="flex-1 flex gap-2 p-4 min-h-0 overflow-hidden">
        {/* Left Data Table - Onset/Start */}
        <Card className="w-64 flex-none flex flex-col overflow-hidden">
          <CardContent className="flex-1 p-0 overflow-hidden">
            <MarkerDataTable type="onset" />
          </CardContent>
        </Card>

        {/* Center - Activity Plot */}
        <div className="flex-1 flex flex-col min-w-0 gap-2">
          {/* Plot */}
          <Card className="flex-1 flex flex-col min-w-0" style={{ minHeight: "350px" }}>
            <CardHeader className="flex-none py-2 px-3">
              <CardTitle className="text-sm">
                {currentFilename ?? "No file selected"} - {currentDate ?? "No date"}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 p-0 relative" style={{ minHeight: "300px" }}>
              {activityLoading || isLoading ? (
                <div className="absolute inset-0 flex items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <ActivityPlot />
              )}
            </CardContent>
          </Card>

          {/* Bottom: Marker lists in a horizontal row */}
          <div className="flex gap-2 h-48">
            {/* Sleep Markers */}
            <Card className="flex-1 flex flex-col overflow-hidden">
              <CardHeader className="flex-none py-2 px-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Moon className="h-4 w-4" />
                  Sleep ({sleepMarkers.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 p-2 overflow-y-auto">
                {sleepMarkers.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Click plot to create</p>
                ) : (
                  <div className="space-y-1">
                    {sleepMarkers.map((marker, index) => (
                      <div
                        key={index}
                        className={`p-1.5 rounded border cursor-pointer transition-colors text-xs ${
                          markerMode === "sleep" && selectedPeriodIndex === index
                            ? "bg-purple-500/10 border-purple-500/50"
                            : "hover:bg-muted"
                        }`}
                        onClick={() => {
                          setMarkerMode("sleep");
                          setSelectedPeriod(index);
                        }}
                      >
                        <div className="flex justify-between items-center">
                          <div>
                            <span className="font-medium text-purple-600 dark:text-purple-400">
                              {marker.markerType}
                            </span>
                            <span className="ml-2">
                              {formatTime(marker.onsetTimestamp)} - {formatTime(marker.offsetTimestamp)}
                            </span>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-5 w-5"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteMarker("sleep", index);
                            }}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Nonwear Markers */}
            <Card className="flex-1 flex flex-col overflow-hidden">
              <CardHeader className="flex-none py-2 px-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Watch className="h-4 w-4" />
                  Nonwear ({nonwearMarkers.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 p-2 overflow-y-auto">
                {nonwearMarkers.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Switch to Nonwear mode</p>
                ) : (
                  <div className="space-y-1">
                    {nonwearMarkers.map((marker, index) => (
                      <div
                        key={index}
                        className={`p-1.5 rounded border cursor-pointer transition-colors text-xs ${
                          markerMode === "nonwear" && selectedPeriodIndex === index
                            ? "bg-orange-500/10 border-orange-500/50"
                            : "hover:bg-muted"
                        }`}
                        onClick={() => {
                          setMarkerMode("nonwear");
                          setSelectedPeriod(index);
                        }}
                      >
                        <div className="flex justify-between items-center">
                          <span>
                            {formatTime(marker.startTimestamp)} - {formatTime(marker.endTimestamp)}
                          </span>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-5 w-5"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteMarker("nonwear", index);
                            }}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

          </div>
        </div>

        {/* Right Data Table - Offset/End */}
        <Card className="w-64 flex-none flex flex-col overflow-hidden">
          <CardContent className="flex-1 p-0 overflow-hidden">
            <MarkerDataTable type="offset" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
