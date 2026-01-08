/**
 * Metrics Panel Component
 *
 * Displays Tudor-Locke sleep quality metrics for the selected sleep period.
 * Metrics are calculated per-sleep-period by the backend.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";
import type { SleepMetrics } from "@/api/types";

interface MetricsPanelProps {
  /** Metrics array from the API (one per sleep period) */
  metrics: SleepMetrics[];
  /** Index of the currently selected period (null if none selected) */
  selectedPeriodIndex: number | null;
  /** Whether the panel is in compact mode */
  compact?: boolean;
}

/**
 * Format minutes as hours and minutes (e.g., "7h 30m")
 */
function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "--";
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours === 0) return `${mins}m`;
  return `${hours}h ${mins}m`;
}

/**
 * Format percentage with one decimal place
 */
function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  return `${value.toFixed(1)}%`;
}

/**
 * Format a numeric value with one decimal place
 */
function formatNumber(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) return "--";
  return value.toFixed(decimals);
}

/**
 * Single metric row component
 */
function MetricRow({
  label,
  value,
  tooltip,
}: {
  label: string;
  value: string;
  tooltip?: string;
}) {
  return (
    <div
      className="flex justify-between items-center py-1 text-sm"
      title={tooltip}
    >
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}

/**
 * Metrics Panel displays Tudor-Locke sleep quality metrics
 */
export function MetricsPanel({
  metrics,
  selectedPeriodIndex,
  compact = false,
}: MetricsPanelProps) {
  // Get metrics for the selected period
  const selectedMetrics =
    selectedPeriodIndex !== null ? metrics[selectedPeriodIndex] : null;

  if (compact) {
    return (
      <Card className="h-full flex flex-col">
        <CardHeader className="flex-none py-2 px-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Metrics
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 p-2 overflow-y-auto">
          {selectedMetrics ? (
            <div className="space-y-0.5 text-xs">
              <MetricRow
                label="TST"
                value={formatMinutes(selectedMetrics.total_sleep_time_minutes)}
                tooltip="Total Sleep Time"
              />
              <MetricRow
                label="SE"
                value={formatPercent(selectedMetrics.sleep_efficiency)}
                tooltip="Sleep Efficiency"
              />
              <MetricRow
                label="WASO"
                value={formatMinutes(selectedMetrics.waso_minutes)}
                tooltip="Wake After Sleep Onset"
              />
              <MetricRow
                label="Awakenings"
                value={String(selectedMetrics.number_of_awakenings ?? "--")}
              />
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Select a sleep marker to view metrics
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="flex-none py-2 px-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <BarChart3 className="h-4 w-4" />
          Sleep Quality Metrics
          {selectedPeriodIndex !== null && (
            <span className="text-muted-foreground font-normal">
              (Period {selectedPeriodIndex + 1})
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-3 overflow-y-auto">
        {selectedMetrics ? (
          <div className="space-y-4">
            {/* Duration Metrics */}
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1 uppercase tracking-wider">
                Duration
              </h4>
              <div className="space-y-0.5">
                <MetricRow
                  label="Time in Bed"
                  value={formatMinutes(selectedMetrics.time_in_bed_minutes)}
                  tooltip="Total time from sleep onset to offset"
                />
                <MetricRow
                  label="Total Sleep Time (TST)"
                  value={formatMinutes(selectedMetrics.total_sleep_time_minutes)}
                  tooltip="Sum of all epochs scored as sleep"
                />
                <MetricRow
                  label="Sleep Onset Latency"
                  value={formatMinutes(selectedMetrics.sleep_onset_latency_minutes)}
                  tooltip="Time from in-bed to first sleep epoch"
                />
                <MetricRow
                  label="WASO"
                  value={formatMinutes(selectedMetrics.waso_minutes)}
                  tooltip="Wake After Sleep Onset - time awake during sleep period"
                />
              </div>
            </div>

            {/* Quality Indices */}
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1 uppercase tracking-wider">
                Quality
              </h4>
              <div className="space-y-0.5">
                <MetricRow
                  label="Sleep Efficiency"
                  value={formatPercent(selectedMetrics.sleep_efficiency)}
                  tooltip="(TST / Time in Bed) × 100"
                />
                <MetricRow
                  label="Movement Index"
                  value={formatPercent(selectedMetrics.movement_index)}
                  tooltip="Percentage of epochs with movement"
                />
                <MetricRow
                  label="Fragmentation Index"
                  value={formatPercent(selectedMetrics.fragmentation_index)}
                  tooltip="Percentage of 1-minute sleep bouts"
                />
                <MetricRow
                  label="Sleep Fragmentation Index"
                  value={formatPercent(selectedMetrics.sleep_fragmentation_index)}
                  tooltip="Movement Index + Fragmentation Index"
                />
              </div>
            </div>

            {/* Awakening Metrics */}
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1 uppercase tracking-wider">
                Awakenings
              </h4>
              <div className="space-y-0.5">
                <MetricRow
                  label="Number of Awakenings"
                  value={String(selectedMetrics.number_of_awakenings ?? "--")}
                  tooltip="Count of distinct wake episodes"
                />
                <MetricRow
                  label="Avg Awakening Length"
                  value={formatMinutes(selectedMetrics.average_awakening_length_minutes)}
                  tooltip="Average duration of wake episodes"
                />
              </div>
            </div>

            {/* Activity Metrics */}
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1 uppercase tracking-wider">
                Activity
              </h4>
              <div className="space-y-0.5">
                <MetricRow
                  label="Total Activity"
                  value={formatNumber(selectedMetrics.total_activity, 0)}
                  tooltip="Sum of activity counts during period"
                />
                <MetricRow
                  label="Nonzero Epochs"
                  value={String(selectedMetrics.nonzero_epochs ?? "--")}
                  tooltip="Count of epochs with activity > 0"
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center">
            <p className="text-sm text-muted-foreground">
              Select a sleep marker to view metrics
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
