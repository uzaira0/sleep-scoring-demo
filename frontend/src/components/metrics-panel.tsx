/**
 * Sleep Metrics Panel Component
 *
 * Displays Tudor-Locke sleep quality metrics for a selected sleep period.
 * Auto-updates when markers change via the store subscription.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";
import type { SleepMetrics } from "@/api/types";

interface MetricsPanelProps {
  metrics: SleepMetrics | null;
  periodIndex: number | null;
  isLoading?: boolean;
}

/**
 * Format a numeric value with specified decimal places
 */
function formatNumber(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) return "--";
  return value.toFixed(decimals);
}

/**
 * Format duration from minutes to hours and minutes
 */
function formatDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "--";
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours > 0) {
    return `${hours}h ${mins}m`;
  }
  return `${mins}m`;
}

/**
 * Format percentage with % symbol
 */
function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  return `${value.toFixed(1)}%`;
}

/**
 * Format datetime string as time (HH:MM)
 */
function formatTime(isoString: string | null | undefined): string {
  if (!isoString) return "--:--";
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
    });
  } catch {
    return "--:--";
  }
}

/**
 * Single metric row component
 */
function MetricRow({
  label,
  value,
  unit,
}: {
  label: string;
  value: string;
  unit?: string;
}) {
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-medium">
        {value}
        {unit && <span className="text-muted-foreground ml-1">{unit}</span>}
      </span>
    </div>
  );
}

/**
 * Section divider component
 */
function MetricSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-2">
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 border-b pb-0.5">
        {title}
      </div>
      {children}
    </div>
  );
}

/**
 * Metrics Panel Component
 *
 * Displays comprehensive Tudor-Locke sleep metrics in a compact card format.
 * Shows duration metrics, quality indices, and activity metrics.
 */
export function MetricsPanel({
  metrics,
  periodIndex,
  isLoading = false,
}: MetricsPanelProps) {
  if (isLoading) {
    return (
      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardHeader className="flex-none py-2 px-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Metrics
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 p-2 text-xs text-muted-foreground">
          Loading...
        </CardContent>
      </Card>
    );
  }

  if (periodIndex === null || !metrics) {
    return (
      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardHeader className="flex-none py-2 px-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Metrics
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 p-2 text-xs text-muted-foreground">
          Select a sleep period to view metrics
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="flex-1 flex flex-col overflow-hidden min-w-[200px]">
      <CardHeader className="flex-none py-2 px-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <BarChart3 className="h-4 w-4" />
          Period {periodIndex + 1} Metrics
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-2 overflow-y-auto">
        {/* Duration Metrics */}
        <MetricSection title="Duration">
          <MetricRow
            label="Time in Bed"
            value={formatDuration(metrics.time_in_bed_minutes)}
          />
          <MetricRow
            label="Total Sleep"
            value={formatDuration(metrics.total_sleep_time_minutes)}
          />
          <MetricRow
            label="WASO"
            value={formatDuration(metrics.waso_minutes)}
          />
          <MetricRow
            label="Sleep Latency"
            value={formatDuration(metrics.sleep_onset_latency_minutes)}
          />
        </MetricSection>

        {/* Quality Indices */}
        <MetricSection title="Quality">
          <MetricRow
            label="Sleep Efficiency"
            value={formatPercent(metrics.sleep_efficiency)}
          />
          <MetricRow
            label="Fragmentation"
            value={formatPercent(metrics.fragmentation_index)}
          />
          <MetricRow
            label="Movement Index"
            value={formatPercent(metrics.movement_index)}
          />
        </MetricSection>

        {/* Awakening Metrics */}
        <MetricSection title="Awakenings">
          <MetricRow
            label="Count"
            value={
              metrics.number_of_awakenings !== null &&
              metrics.number_of_awakenings !== undefined
                ? String(metrics.number_of_awakenings)
                : "--"
            }
          />
          <MetricRow
            label="Avg Length"
            value={formatDuration(metrics.average_awakening_length_minutes)}
          />
        </MetricSection>

        {/* Time Boundaries */}
        <MetricSection title="Times">
          <MetricRow label="In Bed" value={formatTime(metrics.in_bed_time)} />
          <MetricRow label="Out Bed" value={formatTime(metrics.out_bed_time)} />
          <MetricRow
            label="Sleep Onset"
            value={formatTime(metrics.sleep_onset)}
          />
          <MetricRow
            label="Sleep Offset"
            value={formatTime(metrics.sleep_offset)}
          />
        </MetricSection>

        {/* Activity Metrics */}
        <MetricSection title="Activity">
          <MetricRow
            label="Total Counts"
            value={
              metrics.total_activity !== null &&
              metrics.total_activity !== undefined
                ? metrics.total_activity.toLocaleString()
                : "--"
            }
          />
          <MetricRow
            label="Active Epochs"
            value={
              metrics.nonzero_epochs !== null &&
              metrics.nonzero_epochs !== undefined
                ? String(metrics.nonzero_epochs)
                : "--"
            }
          />
        </MetricSection>
      </CardContent>
    </Card>
  );
}
