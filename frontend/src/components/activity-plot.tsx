import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { useActivityData, useMarkers, useSleepScoringStore } from "@/store";
import { useTheme } from "@/components/theme-provider";

/** Epoch duration for timestamp snapping (60 seconds) */
const EPOCH_DURATION_SEC = 60;

/** Snap timestamp to nearest epoch boundary (in seconds) */
function snapToEpoch(timestampSec: number): number {
  return Math.round(timestampSec / EPOCH_DURATION_SEC) * EPOCH_DURATION_SEC;
}

/**
 * Activity data plot using uPlot - renders markers directly into .u-over
 */
export function ActivityPlot() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<uPlot | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const originalXScaleRef = useRef<{ min: number; max: number } | null>(null);
  const isDraggingRef = useRef(false); // Track if currently dragging to prevent re-render
  const { resolvedTheme } = useTheme();

  const { timestamps, axisX, axisY, axisZ, vectorMagnitude, nonwearResults, algorithmResults, preferredDisplayColumn, viewStart, viewEnd } = useActivityData();
  const viewModeHours = useSleepScoringStore((state) => state.viewModeHours);
  const {
    sleepMarkers,
    nonwearMarkers,
    markerMode,
    selectedPeriodIndex,
    creationMode,
    pendingOnsetTimestamp,
    handlePlotClick,
    setSelectedPeriod,
    updateMarker,
    cancelMarkerCreation,
  } = useMarkers();

  // Store current values in refs to avoid stale closures in event handlers
  const stateRef = useRef({
    handlePlotClick,
    sleepMarkers,
    nonwearMarkers,
    markerMode,
    selectedPeriodIndex,
    creationMode,
    pendingOnsetTimestamp,
    setSelectedPeriod,
    updateMarker,
    cancelMarkerCreation,
  });

  // Update refs when values change
  useEffect(() => {
    stateRef.current = {
      handlePlotClick,
      sleepMarkers,
      nonwearMarkers,
      markerMode,
      selectedPeriodIndex,
      creationMode,
      pendingOnsetTimestamp,
      setSelectedPeriod,
      updateMarker,
      cancelMarkerCreation,
    };
  }, [handlePlotClick, sleepMarkers, nonwearMarkers, markerMode, selectedPeriodIndex, creationMode, pendingOnsetTimestamp, setSelectedPeriod, updateMarker, cancelMarkerCreation]);

  const [containerReady, setContainerReady] = useState(false);
  const isDark = resolvedTheme === "dark";

  // ============================================================================
  // CONVERT MASK TO CONTIGUOUS REGIONS
  // ============================================================================
  function maskToRegions(mask: number[], timestamps: number[]): Array<{ startIdx: number; endIdx: number; startTs: number; endTs: number }> {
    const regions: Array<{ startIdx: number; endIdx: number; startTs: number; endTs: number }> = [];
    let regionStart: number | null = null;

    for (let i = 0; i < mask.length; i++) {
      if (mask[i] === 1 && regionStart === null) {
        // Start of a new region
        regionStart = i;
      } else if (mask[i] === 0 && regionStart !== null) {
        // End of current region
        regions.push({
          startIdx: regionStart,
          endIdx: i - 1,
          startTs: timestamps[regionStart],
          endTs: timestamps[i - 1],
        });
        regionStart = null;
      }
    }

    // Handle region that extends to end of data
    if (regionStart !== null) {
      regions.push({
        startIdx: regionStart,
        endIdx: mask.length - 1,
        startTs: timestamps[regionStart],
        endTs: timestamps[mask.length - 1],
      });
    }

    return regions;
  }

  // ============================================================================
  // RENDER MARKERS - Append to wrapper with devicePixelRatio handling for zoom
  // ============================================================================
  function renderMarkers(u: uPlot) {
    if (!u || !u.over) return;

    const over = u.over as HTMLElement;

    const wrapper = over.parentNode as HTMLElement;
    if (!wrapper) return;

    // Clear existing markers from wrapper (including Choi nonwear regions)
    wrapper.querySelectorAll('.marker-region, .marker-line').forEach(el => el.remove());

    // Get plot dimensions accounting for browser zoom (devicePixelRatio)
    const plotLeft = u.bbox.left / devicePixelRatio;
    const plotTop = u.bbox.top / devicePixelRatio;
    const plotWidth = u.bbox.width / devicePixelRatio;
    const plotHeight = u.bbox.height / devicePixelRatio;
    const { sleepMarkers: markers, nonwearMarkers: nwMarkers, markerMode: mode, selectedPeriodIndex: selIdx, creationMode: cMode, pendingOnsetTimestamp: pendingTs } = stateRef.current;

    const sleepColor = isDark ? "rgba(103, 58, 183, 0.3)" : "rgba(103, 58, 183, 0.25)";
    const pendingLineColor = "#888888";
    const sleepLineColor = "#673ab7";
    const nonwearColor = isDark ? "rgba(255, 152, 0, 0.3)" : "rgba(255, 152, 0, 0.25)";
    const nonwearLineColor = "#ff9800";

    // Process sleep markers
    markers.forEach((marker, index) => {
      if (marker.onsetTimestamp === null || marker.offsetTimestamp === null) return;

      const startTs = marker.onsetTimestamp / 1000;
      const endTs = marker.offsetTimestamp / 1000;

      const startPx = u.valToPos(startTs, 'x');
      const endPx = u.valToPos(endTs, 'x');

      if (endPx < 0 || startPx > plotWidth) return;

      const visibleStartPx = Math.max(0, startPx);
      const visibleEndPx = Math.min(plotWidth, endPx);

      const isSelected = mode === "sleep" && selIdx === index;

      // Create shaded region - position relative to wrapper with plotLeft/plotTop offset
      const region = document.createElement('div');
      region.className = 'marker-region sleep';
      region.dataset.markerId = String(index);
      region.dataset.testid = `marker-region-sleep-${index}`;
      region.style.position = 'absolute';
      region.style.left = (plotLeft + visibleStartPx) + 'px';
      region.style.top = plotTop + 'px';
      region.style.width = (visibleEndPx - visibleStartPx) + 'px';
      region.style.height = plotHeight + 'px';
      region.style.background = sleepColor;
      region.style.pointerEvents = 'none';
      region.style.opacity = isSelected ? '1' : '0.8';
      wrapper.appendChild(region);

      // Create lines
      if (startPx >= -10 && startPx <= plotWidth + 10) {
        createMarkerLine(u, wrapper, 'sleep', index, 'start', startPx, plotLeft, plotTop, plotWidth, plotHeight, sleepLineColor, isSelected);
      }
      if (endPx >= -10 && endPx <= plotWidth + 10) {
        createMarkerLine(u, wrapper, 'sleep', index, 'end', endPx, plotLeft, plotTop, plotWidth, plotHeight, sleepLineColor, isSelected);
      }
    });

    // Process nonwear markers
    nwMarkers.forEach((marker, index) => {
      if (marker.startTimestamp === null || marker.endTimestamp === null) return;

      const startTs = marker.startTimestamp / 1000;
      const endTs = marker.endTimestamp / 1000;

      const startPx = u.valToPos(startTs, 'x');
      const endPx = u.valToPos(endTs, 'x');

      if (endPx < 0 || startPx > plotWidth) return;

      const visibleStartPx = Math.max(0, startPx);
      const visibleEndPx = Math.min(plotWidth, endPx);

      const isSelected = mode === "nonwear" && selIdx === index;

      // Position relative to wrapper with plotLeft/plotTop offset
      const region = document.createElement('div');
      region.className = 'marker-region nonwear';
      region.dataset.markerId = String(index);
      region.dataset.testid = `marker-region-nonwear-${index}`;
      region.style.position = 'absolute';
      region.style.left = (plotLeft + visibleStartPx) + 'px';
      region.style.top = plotTop + 'px';
      region.style.width = (visibleEndPx - visibleStartPx) + 'px';
      region.style.height = plotHeight + 'px';
      region.style.background = nonwearColor;
      region.style.pointerEvents = 'none';
      region.style.opacity = isSelected ? '1' : '0.8';
      wrapper.appendChild(region);

      if (startPx >= -10 && startPx <= plotWidth + 10) {
        createMarkerLine(u, wrapper, 'nonwear', index, 'start', startPx, plotLeft, plotTop, plotWidth, plotHeight, nonwearLineColor, isSelected);
      }
      if (endPx >= -10 && endPx <= plotWidth + 10) {
        createMarkerLine(u, wrapper, 'nonwear', index, 'end', endPx, plotLeft, plotTop, plotWidth, plotHeight, nonwearLineColor, isSelected);
      }
    });

    // Render Choi-detected nonwear regions (algorithm-detected, not user-editable)
    // Uses a striped pattern to distinguish from user-placed nonwear markers
    if (nonwearResults && nonwearResults.length > 0 && timestamps.length > 0) {
      const choiRegions = maskToRegions(nonwearResults, timestamps);
      const choiColor = isDark ? "rgba(128, 128, 128, 0.35)" : "rgba(128, 128, 128, 0.25)";

      choiRegions.forEach((region, index) => {
        const startPx = u.valToPos(region.startTs, 'x');
        const endPx = u.valToPos(region.endTs, 'x');

        if (endPx < 0 || startPx > plotWidth) return;

        const visibleStartPx = Math.max(0, startPx);
        const visibleEndPx = Math.min(plotWidth, endPx);

        // Create striped region for Choi nonwear
        const choiRegion = document.createElement('div');
        choiRegion.className = 'marker-region choi-nonwear';
        choiRegion.dataset.choiIndex = String(index);
        choiRegion.dataset.testid = `marker-region-choi-${index}`;
        choiRegion.style.position = 'absolute';
        choiRegion.style.left = (plotLeft + visibleStartPx) + 'px';
        choiRegion.style.top = plotTop + 'px';
        choiRegion.style.width = (visibleEndPx - visibleStartPx) + 'px';
        choiRegion.style.height = plotHeight + 'px';
        choiRegion.style.background = `repeating-linear-gradient(
          45deg,
          ${choiColor},
          ${choiColor} 4px,
          transparent 4px,
          transparent 8px
        )`;
        choiRegion.style.pointerEvents = 'none';
        choiRegion.style.opacity = '0.9';
        wrapper.appendChild(choiRegion);
      });
    }

    // Render pending marker line (grayed out line showing first click position)
    if (cMode === "placing_onset" && pendingTs !== null) {
      const pendingTsSec = pendingTs / 1000;
      const pendingPx = u.valToPos(pendingTsSec, 'x');

      if (pendingPx >= -10 && pendingPx <= plotWidth + 10) {
        const pendingLine = document.createElement('div');
        pendingLine.className = 'marker-line pending';
        pendingLine.dataset.testid = 'marker-line-pending';
        pendingLine.style.position = 'absolute';
        pendingLine.style.left = (plotLeft + pendingPx - 2) + 'px';
        pendingLine.style.top = plotTop + 'px';
        pendingLine.style.width = '4px';
        pendingLine.style.height = plotHeight + 'px';
        pendingLine.style.background = pendingLineColor;
        pendingLine.style.opacity = '0.7';
        pendingLine.style.pointerEvents = 'none';
        pendingLine.style.borderStyle = 'dashed';
        wrapper.appendChild(pendingLine);
      }
    }
  }

  // ============================================================================
  // CREATE MARKER LINE - Append to wrapper with devicePixelRatio positioning
  // ============================================================================
  function createMarkerLine(
    u: uPlot,
    wrapper: HTMLElement,
    type: 'sleep' | 'nonwear',
    index: number,
    edge: 'start' | 'end',
    px: number,
    plotLeft: number,
    plotTop: number,
    plotWidth: number,
    plotHeight: number,
    color: string,
    isSelected: boolean
  ) {
    const line = document.createElement('div');
    line.className = `marker-line ${type}-${edge}`;
    line.dataset.testid = `marker-line-${type}-${index}-${edge}`;
    line.style.position = 'absolute';
    line.style.left = (plotLeft + px - 6) + 'px';
    line.style.top = plotTop + 'px';
    line.style.width = '12px';
    line.style.height = plotHeight + 'px';
    line.style.cursor = 'ew-resize';
    line.style.zIndex = '10';
    line.style.pointerEvents = 'auto';

    // Inner line visual
    const inner = document.createElement('div');
    inner.style.position = 'absolute';
    inner.style.left = '50%';
    inner.style.top = '0';
    inner.style.bottom = '0';
    inner.style.width = isSelected ? '4px' : '2px';
    inner.style.transform = 'translateX(-50%)';
    inner.style.background = color;
    line.appendChild(inner);

    // Drag state
    let isDragging = false;
    let dragStartX = 0;
    let dragStartLeft = 0;

    line.addEventListener('mousedown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      isDragging = true;
      isDraggingRef.current = true; // Prevent re-renders during drag
      dragStartX = e.clientX;
      dragStartLeft = parseFloat(line.style.left);
      inner.style.width = '4px';
      line.classList.add('dragging');

      const onMouseMove = (e: MouseEvent) => {
        if (!isDragging) return;
        const dx = e.clientX - dragStartX;
        let newLeft = dragStartLeft + dx;
        // Clamp to plot boundaries
        const minLeft = plotLeft - 6;
        const maxLeft = plotLeft + plotWidth - 6;
        newLeft = Math.max(minLeft, Math.min(maxLeft, newLeft));
        line.style.left = newLeft + 'px';

        // Calculate pixel position for region update
        const linePx = newLeft - plotLeft + 6;

        // Calculate and update position in real-time (store won't trigger re-render because isDraggingRef is true)
        const lineRect = line.getBoundingClientRect();
        const rootRect = u.root.getBoundingClientRect();
        const currentPx = (lineRect.left + 6) - rootRect.left - plotLeft;
        const currentTs = u.posToVal(currentPx, 'x');
        if (currentTs !== undefined && currentTs !== null) {
          const snappedSec = snapToEpoch(currentTs);
          const timestampMs = snappedSec * 1000;

          // Update the shaded region in real-time
          const region = wrapper.querySelector(`.marker-region.${type}[data-marker-id="${index}"]`) as HTMLElement;
          if (region) {
            // Get the other edge's position from current marker state
            const markers = type === 'sleep' ? stateRef.current.sleepMarkers : stateRef.current.nonwearMarkers;
            const marker = markers[index];
            if (marker) {
              let startPx: number, endPx: number;
              if (type === 'sleep') {
                const m = marker as { onsetTimestamp: number | null; offsetTimestamp: number | null };
                if (edge === 'start') {
                  startPx = linePx;
                  endPx = m.offsetTimestamp !== null ? u.valToPos(m.offsetTimestamp / 1000, 'x') : linePx;
                } else {
                  startPx = m.onsetTimestamp !== null ? u.valToPos(m.onsetTimestamp / 1000, 'x') : linePx;
                  endPx = linePx;
                }
              } else {
                const m = marker as { startTimestamp: number | null; endTimestamp: number | null };
                if (edge === 'start') {
                  startPx = linePx;
                  endPx = m.endTimestamp !== null ? u.valToPos(m.endTimestamp / 1000, 'x') : linePx;
                } else {
                  startPx = m.startTimestamp !== null ? u.valToPos(m.startTimestamp / 1000, 'x') : linePx;
                  endPx = linePx;
                }
              }
              // Ensure proper order (start < end)
              const left = Math.min(startPx, endPx);
              const right = Math.max(startPx, endPx);
              const visibleLeft = Math.max(0, left);
              const visibleRight = Math.min(plotWidth, right);
              region.style.left = (plotLeft + visibleLeft) + 'px';
              region.style.width = Math.max(0, visibleRight - visibleLeft) + 'px';
            }
          }

          if (type === 'sleep') {
            const updates = edge === 'start'
              ? { onsetTimestamp: timestampMs }
              : { offsetTimestamp: timestampMs };
            stateRef.current.updateMarker(type, index, updates);
          } else {
            const updates = edge === 'start'
              ? { startTimestamp: timestampMs }
              : { endTimestamp: timestampMs };
            stateRef.current.updateMarker(type, index, updates);
          }
        }
      };

      const onMouseUp = () => {
        if (!isDragging) return;
        isDragging = false;
        isDraggingRef.current = false; // Allow re-renders again
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        inner.style.width = isSelected ? '4px' : '2px';

        // Final position update
        const lineRect = line.getBoundingClientRect();
        const rootRect = u.root.getBoundingClientRect();
        const finalPx = (lineRect.left + 6) - rootRect.left - plotLeft;
        const newTs = u.posToVal(finalPx, 'x');
        if (newTs === undefined || newTs === null) return;

        const snappedSec = snapToEpoch(newTs);
        const timestampMs = snappedSec * 1000;

        if (type === 'sleep') {
          const updates = edge === 'start'
            ? { onsetTimestamp: timestampMs }
            : { offsetTimestamp: timestampMs };
          stateRef.current.updateMarker(type, index, updates);
        } else {
          const updates = edge === 'start'
            ? { startTimestamp: timestampMs }
            : { endTimestamp: timestampMs };
          stateRef.current.updateMarker(type, index, updates);
        }

        // Select this period and trigger final re-render
        stateRef.current.setSelectedPeriod(index);
        // Force re-render markers after drag
        if (chartRef.current) {
          renderMarkers(chartRef.current);
        }
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });

    // Forward wheel events to chart for zoom
    line.addEventListener('wheel', (e) => {
      e.preventDefault();
      e.stopPropagation();
      u.root.dispatchEvent(new WheelEvent('wheel', {
        deltaY: e.deltaY,
        clientX: e.clientX,
        clientY: e.clientY,
        bubbles: true,
      }));
    }, { passive: false });

    wrapper.appendChild(line);
  }

  // ============================================================================
  // WHEEL ZOOM PLUGIN - EXACT COPY FROM benchmark.html
  // ============================================================================
  function wheelZoomPlugin(factor: number) {
    return {
      hooks: {
        ready: (u: uPlot) => {
          const wrapper = u.root;

          // Wheel zoom
          wrapper.addEventListener('wheel', (e: WheelEvent) => {
            e.preventDefault();
            e.stopPropagation();

            const rect = u.over.getBoundingClientRect();
            const left = e.clientX - rect.left;

            if (left < 0 || left > rect.width) return;

            const xVal = u.posToVal(left, 'x');
            const oxRange = (u.scales.x.max ?? 0) - (u.scales.x.min ?? 0);

            const nxRange = e.deltaY > 0 ? oxRange / factor : oxRange * factor;
            const minRange = 60;
            const maxRange = originalXScaleRef.current
              ? (originalXScaleRef.current.max - originalXScaleRef.current.min)
              : oxRange * 10;

            if (nxRange < minRange || nxRange > maxRange) return;

            const leftPct = left / (u.bbox.width / devicePixelRatio);
            const nxMin = xVal - leftPct * nxRange;
            const nxMax = nxMin + nxRange;

            u.batch(() => {
              u.setScale('x', { min: nxMin, max: nxMax });
            });
          }, { passive: false });

          // Pan with middle mouse or shift+drag
          let isPanning = false;
          let panStartX = 0;
          let panStartMin = 0;
          let panStartMax = 0;

          u.over.addEventListener('mousedown', (e: MouseEvent) => {
            if (e.button === 1 || (e.button === 0 && e.shiftKey)) {
              e.preventDefault();
              isPanning = true;
              panStartX = e.clientX;
              panStartMin = u.scales.x.min ?? 0;
              panStartMax = u.scales.x.max ?? 0;
              u.over.style.cursor = 'grabbing';
            }
          });

          document.addEventListener('mousemove', (e: MouseEvent) => {
            if (!isPanning) return;
            const dx = e.clientX - panStartX;
            const pxPerVal = (u.bbox.width / devicePixelRatio) / (panStartMax - panStartMin);
            const dVal = -dx / pxPerVal;

            let nxMin = panStartMin + dVal;
            let nxMax = panStartMax + dVal;

            if (originalXScaleRef.current) {
              if (nxMin < originalXScaleRef.current.min) {
                nxMax += (originalXScaleRef.current.min - nxMin);
                nxMin = originalXScaleRef.current.min;
              }
              if (nxMax > originalXScaleRef.current.max) {
                nxMin -= (nxMax - originalXScaleRef.current.max);
                nxMax = originalXScaleRef.current.max;
              }
            }

            u.batch(() => {
              u.setScale('x', { min: nxMin, max: nxMax });
            });
          });

          document.addEventListener('mouseup', () => {
            if (isPanning) {
              isPanning = false;
              u.over.style.cursor = 'crosshair';
            }
          });

          // Click handler for marker placement - EXACT from benchmark.html
          u.over.addEventListener('click', (e: MouseEvent) => {
            const rect = u.over.getBoundingClientRect();
            const left = e.clientX - rect.left;

            if (left < 0 || left > rect.width) return;

            const ts = u.posToVal(left, 'x');
            if (ts === undefined || ts === null) return;

            const snappedSec = snapToEpoch(ts);
            stateRef.current.handlePlotClick(snappedSec * 1000);
          });

          // Right-click handler to cancel marker placement
          u.over.addEventListener('contextmenu', (e: MouseEvent) => {
            e.preventDefault();
            // Cancel marker creation if in progress
            if (stateRef.current.creationMode !== 'idle') {
              stateRef.current.cancelMarkerCreation();
            }
          });

          // Initial marker render
          renderMarkers(u);
        },
        setScale: [(u: uPlot, key: string) => {
          if (key === 'x') {
            renderMarkers(u);
          }
        }],
      },
    };
  }

  // Wait for container to have dimensions
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setContainerReady(true);
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // ============================================================================
  // CREATE CHART - EXACT STRUCTURE FROM benchmark.html
  // ============================================================================
  useEffect(() => {
    if (!containerRef.current || !containerReady) return;
    if (timestamps.length === 0) return;

    const container = containerRef.current;
    // Select display data based on user preference
    const displayData = (() => {
      switch (preferredDisplayColumn) {
        case "axis_x": return axisX;
        case "axis_y": return axisY;
        case "axis_z": return axisZ;
        case "vector_magnitude": return vectorMagnitude;
        default: return axisY;
      }
    })();
    if (displayData.length === 0) return;

    // Destroy existing chart
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }

    // Remove old marker elements
    document.querySelectorAll('.marker-line, .marker-region').forEach(el => el.remove());

    const width = container.clientWidth || 800;
    const height = 380;

    // Use view range from backend if available, otherwise fall back to data range
    // This ensures the full expected range is shown even if data is missing at edges
    const dataMin = timestamps[0];
    const dataMax = timestamps[timestamps.length - 1];
    const initialMin = viewStart ?? dataMin;
    const initialMax = viewEnd ?? dataMax;
    originalXScaleRef.current = { min: initialMin, max: initialMax };

    // uPlot options
    const opts: uPlot.Options = {
      width,
      height,
      plugins: [wheelZoomPlugin(0.75)],
      legend: { show: false }, // Hide legend - we show info in sidebar
      scales: {
        x: {
          time: true,
          min: initialMin,
          max: initialMax,
        },
        y: { auto: true },
      },
      axes: [
        {
          stroke: isDark ? '#888' : '#666',
          grid: { stroke: isDark ? '#333' : '#ddd', width: 1 },
          ticks: { stroke: isDark ? '#444' : '#999' },
          // Format x-axis times in UTC to match stored data (no timezone conversion)
          values: (_u: uPlot, vals: number[]) => vals.map(v => {
            const d = new Date(v * 1000);
            // Use UTC methods to avoid local timezone conversion
            const hours = String(d.getUTCHours()).padStart(2, '0');
            const mins = String(d.getUTCMinutes()).padStart(2, '0');
            return `${hours}:${mins}`;
          }),
        },
        {
          stroke: isDark ? '#888' : '#666',
          grid: { stroke: isDark ? '#333' : '#ddd', width: 1 },
          ticks: { stroke: isDark ? '#444' : '#999' },
        },
      ],
      series: [
        {},
        {
          stroke: isDark ? '#4fc3f7' : '#0ea5e9',
          width: 1,
          fill: isDark ? 'rgba(79, 195, 247, 0.1)' : 'rgba(14, 165, 233, 0.1)',
        },
      ],
      cursor: {
        drag: { x: false, y: false },
        sync: { key: 'activity' },
        focus: { prox: 30 },
        points: {
          show: true,
          size: 8,
          fill: isDark ? '#4fc3f7' : '#0ea5e9',
          stroke: isDark ? '#fff' : '#000',
          width: 2,
        },
      },
      hooks: {
        setCursor: [(u: uPlot) => {
          const tooltip = tooltipRef.current;
          if (!tooltip) return;
          
          const { left, top, idx } = u.cursor;
          
          if (idx === null || idx === undefined || left === undefined || top === undefined || left < 0) {
            tooltip.style.display = 'none';
            return;
          }
          
          const ts = u.data[0][idx];
          const val = u.data[1][idx];
          
          if (ts === undefined || val === undefined) {
            tooltip.style.display = 'none';
            return;
          }
          
          // Format timestamp in UTC to match stored data (no timezone conversion)
          const date = new Date(ts * 1000);
          const timeStr = date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
            timeZone: 'UTC',
          });
          const dateStr = date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            timeZone: 'UTC',
          });
          
          // Update tooltip content
          tooltip.innerHTML = `
            <div style="font-weight: 600; margin-bottom: 4px;">${dateStr} ${timeStr}</div>
            <div>Value: <span style="font-weight: 600;">${val.toFixed(1)}</span></div>
          `;
          
          // Position tooltip near cursor but keep in bounds
          const plotLeft = u.bbox.left / devicePixelRatio;
          const plotTop = u.bbox.top / devicePixelRatio;
          const plotWidth = u.bbox.width / devicePixelRatio;
          
          let tooltipX = plotLeft + left + 12;
          let tooltipY = plotTop + top - 40;
          
          // Keep tooltip in bounds
          const tooltipWidth = 140;
          if (tooltipX + tooltipWidth > plotLeft + plotWidth) {
            tooltipX = plotLeft + left - tooltipWidth - 12;
          }
          if (tooltipY < plotTop) {
            tooltipY = plotTop + top + 12;
          }
          
          tooltip.style.left = tooltipX + 'px';
          tooltip.style.top = tooltipY + 'px';
          tooltip.style.display = 'block';
        }],
      },
    };

    const chartData: uPlot.AlignedData = [timestamps, displayData];
    chartRef.current = new uPlot(opts, chartData, container);

    // Handle resize
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (chartRef.current && width > 0) {
          chartRef.current.setSize({ width, height: 380 });
        }
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [timestamps, axisX, axisY, axisZ, vectorMagnitude, preferredDisplayColumn, viewModeHours, containerReady, isDark, viewStart, viewEnd]);

  // Re-render markers when marker state changes (skip during drag to prevent DOM destruction)
  useEffect(() => {
    if (chartRef.current && !isDraggingRef.current) {
      renderMarkers(chartRef.current);
    }
  }, [sleepMarkers, nonwearMarkers, nonwearResults, selectedPeriodIndex, markerMode, creationMode, pendingOnsetTimestamp]);

  if (timestamps.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-muted-foreground">
        No activity data available
      </div>
    );
  }

  return (
    <div className="w-full relative" style={{ height: '380px', overflow: 'hidden' }}>
      <div ref={containerRef} className="w-full h-full" />
      <div
        ref={tooltipRef}
        className="absolute pointer-events-none z-50 px-3 py-2 rounded-md shadow-lg text-sm"
        style={{
          display: 'none',
          backgroundColor: isDark ? 'rgba(30, 30, 50, 0.95)' : 'rgba(255, 255, 255, 0.95)',
          color: isDark ? '#e0e0e0' : '#333',
          border: isDark ? '1px solid #444' : '1px solid #ddd',
          minWidth: '120px',
        }}
      />
    </div>
  );
}
