import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import { useShallow } from "zustand/react/shallow";

/**
 * User authentication state
 */
interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: {
    id: number;
    email: string;
    username: string;
    role: string;
  } | null;
  isAuthenticated: boolean;
}

/**
 * File and date selection state
 */
interface FileState {
  currentFileId: number | null;
  currentFilename: string | null;
  currentDateIndex: number;
  availableDates: string[];
  availableFiles: Array<{
    id: number;
    filename: string;
    status: string;
    rowCount: number | null;
  }>;
}

/**
 * Activity data state (columnar format)
 */
interface ActivityState {
  timestamps: number[];
  axisX: number[];
  axisY: number[];
  axisZ: number[];
  vectorMagnitude: number[];
  algorithmResults: number[] | null;  // Sleep scoring (1=sleep, 0=wake)
  nonwearResults: number[] | null;  // Choi nonwear (1=nonwear, 0=wear)
  isLoading: boolean;
  // Expected view range (for setting axis bounds even if data is missing)
  viewStart: number | null;
  viewEnd: number | null;
}

/**
 * Marker creation state machine
 */
type MarkerCreationMode = "idle" | "placing_onset" | "placing_offset";
type MarkerMode = "sleep" | "nonwear";

/**
 * Marker state
 */
interface MarkerState {
  sleepMarkers: Array<{
    onsetTimestamp: number | null;
    offsetTimestamp: number | null;
    markerIndex: number;
    markerType: "MAIN_SLEEP" | "NAP";
  }>;
  nonwearMarkers: Array<{
    startTimestamp: number | null;
    endTimestamp: number | null;
    markerIndex: number;
  }>;
  isDirty: boolean;
  isSaving: boolean;
  lastSavedAt: number | null;
  saveError: string | null;
  selectedPeriodIndex: number | null;

  // Two-click marker creation state
  markerMode: MarkerMode;
  creationMode: MarkerCreationMode;
  pendingOnsetTimestamp: number | null;
}

/**
 * Display preferences state
 */
interface PreferencesState {
  preferredDisplayColumn: "axis_x" | "axis_y" | "axis_z" | "vector_magnitude";
  viewModeHours: 24 | 48;
  currentAlgorithm: string;
}

/**
 * Study settings state (mirrors PyQt study_settings_tab.py)
 * Note: Only epoch-based paradigm for now, no raw/GT3X support
 */
interface StudySettingsState {
  sleepDetectionRule: "consecutive_onset3s_offset5s" | "consecutive_onset5s_offset10s" | "tudor_locke_2014";
  nightStartHour: string; // "21:00" format
  nightEndHour: string;   // "09:00" format
  // Note: nonwearAlgorithm is always "choi_2011" for epoch data (no van_hees)
}

/**
 * Data settings state (mirrors PyQt data_settings_tab.py)
 * Note: Only CSV/epoch-based for now, no GT3X/raw support
 */
interface DataSettingsState {
  devicePreset: "actigraph" | "actiwatch" | "motionwatch" | "geneactiv" | "generic";
  epochLengthSeconds: number;
  skipRows: number;
}

/**
 * Combined store state
 */
interface SleepScoringState
  extends AuthState,
    FileState,
    ActivityState,
    MarkerState,
    PreferencesState,
    StudySettingsState,
    DataSettingsState {
  // Auth actions
  setAuth: (
    accessToken: string,
    refreshToken: string,
    user: AuthState["user"]
  ) => void;
  clearAuth: () => void;

  // File actions
  setCurrentFile: (fileId: number, filename: string) => void;
  setAvailableFiles: (files: FileState["availableFiles"]) => void;
  setAvailableDates: (dates: string[]) => void;
  setCurrentDateIndex: (index: number) => void;
  navigateDate: (direction: 1 | -1) => void;

  // Activity data actions
  setActivityData: (data: {
    timestamps: number[];
    axisX: number[];
    axisY: number[];
    axisZ: number[];
    vectorMagnitude: number[];
    algorithmResults?: number[] | null;
    nonwearResults?: number[] | null;
    viewStart?: number | null;
    viewEnd?: number | null;
  }) => void;
  setLoading: (loading: boolean) => void;
  clearActivityData: () => void;

  // Marker actions
  setSleepMarkers: (markers: MarkerState["sleepMarkers"]) => void;
  setNonwearMarkers: (markers: MarkerState["nonwearMarkers"]) => void;
  setMarkersDirty: (dirty: boolean) => void;
  setSelectedPeriod: (index: number | null) => void;

  // Two-click marker creation actions
  setMarkerMode: (mode: MarkerMode) => void;
  handlePlotClick: (timestamp: number) => void;
  cancelMarkerCreation: () => void;
  addSleepMarker: (
    onsetTimestamp: number,
    offsetTimestamp: number,
    markerType?: "MAIN_SLEEP" | "NAP"
  ) => void;
  addNonwearMarker: (startTimestamp: number, endTimestamp: number) => void;
  updateMarker: (
    category: "sleep" | "nonwear",
    index: number,
    updates: Partial<{
      onsetTimestamp: number;
      offsetTimestamp: number;
      startTimestamp: number;
      endTimestamp: number;
    }>
  ) => void;
  deleteMarker: (category: "sleep" | "nonwear", index: number) => void;

  // Save status actions
  setSaving: (saving: boolean) => void;
  setSaveError: (error: string | null) => void;
  markSaved: () => void;

  // Preferences actions
  setPreferredDisplayColumn: (
    column: PreferencesState["preferredDisplayColumn"]
  ) => void;
  setViewModeHours: (hours: PreferencesState["viewModeHours"]) => void;
  setCurrentAlgorithm: (algorithm: string) => void;

  // Study settings actions
  setSleepDetectionRule: (rule: StudySettingsState["sleepDetectionRule"]) => void;
  setNightHours: (startHour: string, endHour: string) => void;

  // Data settings actions
  setDevicePreset: (preset: DataSettingsState["devicePreset"]) => void;
  setEpochLengthSeconds: (seconds: number) => void;
  setSkipRows: (rows: number) => void;
}

/**
 * Main Zustand store for Sleep Scoring application.
 * Mirrors the desktop app's Redux store pattern.
 */
export const useSleepScoringStore = create<SleepScoringState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial auth state
        accessToken: null,
        refreshToken: null,
        user: null,
        isAuthenticated: false,

        // Initial file state
        currentFileId: null,
        currentFilename: null,
        currentDateIndex: 0,
        availableDates: [],
        availableFiles: [],

        // Initial activity state
        timestamps: [],
        axisX: [],
        axisY: [],
        axisZ: [],
        vectorMagnitude: [],
        algorithmResults: null,
        nonwearResults: null,
        isLoading: false,
        viewStart: null,
        viewEnd: null,

        // Initial marker state
        sleepMarkers: [],
        nonwearMarkers: [],
        isDirty: false,
        isSaving: false,
        lastSavedAt: null,
        saveError: null,
        selectedPeriodIndex: null,

        // Two-click marker creation state
        markerMode: "sleep",
        creationMode: "idle",
        pendingOnsetTimestamp: null,

        // Initial preferences
        preferredDisplayColumn: "axis_y",
        viewModeHours: 24,
        currentAlgorithm: "sadeh_1994_actilife",

        // Initial study settings
        sleepDetectionRule: "consecutive_onset3s_offset5s",
        nightStartHour: "21:00",
        nightEndHour: "09:00",

        // Initial data settings
        devicePreset: "actigraph",
        epochLengthSeconds: 60,
        skipRows: 10,

        // Auth actions
        setAuth: (accessToken, refreshToken, user) =>
          set({
            accessToken,
            refreshToken,
            user,
            isAuthenticated: true,
          }),

        clearAuth: () =>
          set({
            accessToken: null,
            refreshToken: null,
            user: null,
            isAuthenticated: false,
          }),

        // File actions
        setCurrentFile: (fileId, filename) =>
          set({
            currentFileId: fileId,
            currentFilename: filename,
            currentDateIndex: 0,
            timestamps: [],
            axisX: [],
            axisY: [],
            axisZ: [],
            vectorMagnitude: [],
            algorithmResults: null,
            nonwearResults: null,
            viewStart: null,
            viewEnd: null,
          }),

        setAvailableFiles: (files) => set({ availableFiles: files }),

        setAvailableDates: (dates) => set({ availableDates: dates }),

        setCurrentDateIndex: (index) => set({ currentDateIndex: index }),

        navigateDate: (direction) => {
          const { currentDateIndex, availableDates } = get();
          const newIndex = currentDateIndex + direction;
          if (newIndex >= 0 && newIndex < availableDates.length) {
            set({ currentDateIndex: newIndex });
          }
        },

        // Activity data actions
        setActivityData: (data) =>
          set({
            timestamps: data.timestamps,
            axisX: data.axisX,
            axisY: data.axisY,
            axisZ: data.axisZ,
            vectorMagnitude: data.vectorMagnitude,
            algorithmResults: data.algorithmResults ?? null,
            nonwearResults: data.nonwearResults ?? null,
            viewStart: data.viewStart ?? null,
            viewEnd: data.viewEnd ?? null,
            isLoading: false,
          }),

        setLoading: (loading) => set({ isLoading: loading }),

        clearActivityData: () =>
          set({
            timestamps: [],
            axisX: [],
            axisY: [],
            axisZ: [],
            vectorMagnitude: [],
            algorithmResults: null,
            nonwearResults: null,
            viewStart: null,
            viewEnd: null,
          }),

        // Marker actions
        setSleepMarkers: (markers) =>
          set({ sleepMarkers: markers, isDirty: true }),

        setNonwearMarkers: (markers) =>
          set({ nonwearMarkers: markers, isDirty: true }),

        setMarkersDirty: (dirty) => set({ isDirty: dirty }),

        setSelectedPeriod: (index) => set({ selectedPeriodIndex: index }),

        // Two-click marker creation actions
        setMarkerMode: (mode) =>
          set({ markerMode: mode, creationMode: "idle", pendingOnsetTimestamp: null }),

        handlePlotClick: (timestamp) => {
          const { markerMode, creationMode, pendingOnsetTimestamp, sleepMarkers, nonwearMarkers } = get();

          if (creationMode === "idle") {
            // First click: set onset/start
            set({ creationMode: "placing_onset", pendingOnsetTimestamp: timestamp });
          } else if (creationMode === "placing_onset" && pendingOnsetTimestamp !== null) {
            // Second click: complete the marker
            const onset = Math.min(pendingOnsetTimestamp, timestamp);
            const offset = Math.max(pendingOnsetTimestamp, timestamp);

            if (markerMode === "sleep") {
              // Determine marker type: first is MAIN_SLEEP, others are NAP
              const markerType = sleepMarkers.length === 0 ? "MAIN_SLEEP" : "NAP";
              const newMarkerIndex = sleepMarkers.length;
              const newMarker = {
                onsetTimestamp: onset,
                offsetTimestamp: offset,
                markerIndex: newMarkerIndex,
                markerType: markerType as "MAIN_SLEEP" | "NAP",
              };
              set({
                sleepMarkers: [...sleepMarkers, newMarker],
                isDirty: true,
                creationMode: "idle",
                pendingOnsetTimestamp: null,
                selectedPeriodIndex: newMarkerIndex, // Select newly created marker
              });
            } else {
              // Nonwear marker
              const newMarkerIndex = nonwearMarkers.length;
              const newMarker = {
                startTimestamp: onset,
                endTimestamp: offset,
                markerIndex: newMarkerIndex,
              };
              set({
                nonwearMarkers: [...nonwearMarkers, newMarker],
                isDirty: true,
                creationMode: "idle",
                pendingOnsetTimestamp: null,
                selectedPeriodIndex: newMarkerIndex, // Select newly created marker
              });
            }
          }
        },

        cancelMarkerCreation: () =>
          set({ creationMode: "idle", pendingOnsetTimestamp: null }),

        addSleepMarker: (onsetTimestamp, offsetTimestamp, markerType) => {
          const { sleepMarkers } = get();
          const newMarker = {
            onsetTimestamp,
            offsetTimestamp,
            markerIndex: sleepMarkers.length,
            markerType: markerType ?? (sleepMarkers.length === 0 ? "MAIN_SLEEP" : "NAP") as "MAIN_SLEEP" | "NAP",
          };
          set({
            sleepMarkers: [...sleepMarkers, newMarker],
            isDirty: true,
          });
        },

        addNonwearMarker: (startTimestamp, endTimestamp) => {
          const { nonwearMarkers } = get();
          const newMarker = {
            startTimestamp,
            endTimestamp,
            markerIndex: nonwearMarkers.length,
          };
          set({
            nonwearMarkers: [...nonwearMarkers, newMarker],
            isDirty: true,
          });
        },

        updateMarker: (category, index, updates) => {
          if (category === "sleep") {
            const { sleepMarkers } = get();
            const updated = sleepMarkers.map((m, i) =>
              i === index ? { ...m, ...updates } : m
            );
            set({ sleepMarkers: updated, isDirty: true });
          } else {
            const { nonwearMarkers } = get();
            const updated = nonwearMarkers.map((m, i) =>
              i === index ? { ...m, ...updates } : m
            );
            set({ nonwearMarkers: updated, isDirty: true });
          }
        },

        deleteMarker: (category, index) => {
          if (category === "sleep") {
            const { sleepMarkers } = get();
            const updated = sleepMarkers
              .filter((_, i) => i !== index)
              .map((m, i) => ({ ...m, markerIndex: i }));
            set({ sleepMarkers: updated, isDirty: true, selectedPeriodIndex: null });
          } else {
            const { nonwearMarkers } = get();
            const updated = nonwearMarkers
              .filter((_, i) => i !== index)
              .map((m, i) => ({ ...m, markerIndex: i }));
            set({ nonwearMarkers: updated, isDirty: true, selectedPeriodIndex: null });
          }
        },

        // Save status actions
        setSaving: (saving) => set({ isSaving: saving }),
        setSaveError: (error) => set({ saveError: error }),
        markSaved: () => set({ isDirty: false, isSaving: false, lastSavedAt: Date.now() }),

        // Preferences actions
        setPreferredDisplayColumn: (column) =>
          set({ preferredDisplayColumn: column }),

        setViewModeHours: (hours) => set({ viewModeHours: hours }),

        setCurrentAlgorithm: (algorithm) =>
          set({ currentAlgorithm: algorithm }),

        // Study settings actions
        setSleepDetectionRule: (rule) => set({ sleepDetectionRule: rule }),

        setNightHours: (startHour, endHour) =>
          set({ nightStartHour: startHour, nightEndHour: endHour }),

        // Data settings actions
        setDevicePreset: (preset) => set({ devicePreset: preset }),

        setEpochLengthSeconds: (seconds) => set({ epochLengthSeconds: seconds }),

        setSkipRows: (rows) => set({ skipRows: rows }),
      }),
      {
        name: "sleep-scoring-storage",
        partialize: (state) => ({
          // Only persist these fields
          accessToken: state.accessToken,
          refreshToken: state.refreshToken,
          user: state.user,
          isAuthenticated: state.isAuthenticated,
          // Preferences
          preferredDisplayColumn: state.preferredDisplayColumn,
          viewModeHours: state.viewModeHours,
          currentAlgorithm: state.currentAlgorithm,
          // Study settings
          sleepDetectionRule: state.sleepDetectionRule,
          nightStartHour: state.nightStartHour,
          nightEndHour: state.nightEndHour,
          // Data settings
          devicePreset: state.devicePreset,
          epochLengthSeconds: state.epochLengthSeconds,
          skipRows: state.skipRows,
        }),
      }
    ),
    { name: "SleepScoringStore" }
  )
);

// Selector hooks for specific state slices
// Using useShallow to prevent infinite re-renders from object selectors
export const useAuth = () =>
  useSleepScoringStore(
    useShallow((state) => ({
      accessToken: state.accessToken,
      user: state.user,
      isAuthenticated: state.isAuthenticated,
      setAuth: state.setAuth,
      clearAuth: state.clearAuth,
    }))
  );

export const useFiles = () =>
  useSleepScoringStore(
    useShallow((state) => ({
      currentFileId: state.currentFileId,
      currentFilename: state.currentFilename,
      availableFiles: state.availableFiles,
      setCurrentFile: state.setCurrentFile,
      setAvailableFiles: state.setAvailableFiles,
    }))
  );

export const useActivityData = () =>
  useSleepScoringStore(
    useShallow((state) => ({
      timestamps: state.timestamps,
      axisX: state.axisX,
      axisY: state.axisY,
      axisZ: state.axisZ,
      vectorMagnitude: state.vectorMagnitude,
      algorithmResults: state.algorithmResults,
      nonwearResults: state.nonwearResults,
      isLoading: state.isLoading,
      preferredDisplayColumn: state.preferredDisplayColumn,
      viewStart: state.viewStart,
      viewEnd: state.viewEnd,
      setActivityData: state.setActivityData,
      setLoading: state.setLoading,
    }))
  );

export const useDates = () =>
  useSleepScoringStore(
    useShallow((state) => ({
      currentDateIndex: state.currentDateIndex,
      availableDates: state.availableDates,
      currentDate: state.availableDates[state.currentDateIndex] ?? null,
      setAvailableDates: state.setAvailableDates,
      setCurrentDateIndex: state.setCurrentDateIndex,
      navigateDate: state.navigateDate,
    }))
  );

export const useMarkers = () =>
  useSleepScoringStore(
    useShallow((state) => ({
      // Marker data
      sleepMarkers: state.sleepMarkers,
      nonwearMarkers: state.nonwearMarkers,
      isDirty: state.isDirty,
      selectedPeriodIndex: state.selectedPeriodIndex,

      // Two-click creation state
      markerMode: state.markerMode,
      creationMode: state.creationMode,
      pendingOnsetTimestamp: state.pendingOnsetTimestamp,

      // Save status
      isSaving: state.isSaving,
      lastSavedAt: state.lastSavedAt,
      saveError: state.saveError,

      // Basic marker actions
      setSleepMarkers: state.setSleepMarkers,
      setNonwearMarkers: state.setNonwearMarkers,
      setMarkersDirty: state.setMarkersDirty,
      setSelectedPeriod: state.setSelectedPeriod,

      // Two-click creation actions
      setMarkerMode: state.setMarkerMode,
      handlePlotClick: state.handlePlotClick,
      cancelMarkerCreation: state.cancelMarkerCreation,
      addSleepMarker: state.addSleepMarker,
      addNonwearMarker: state.addNonwearMarker,
      updateMarker: state.updateMarker,
      deleteMarker: state.deleteMarker,

      // Save status actions
      setSaving: state.setSaving,
      setSaveError: state.setSaveError,
      markSaved: state.markSaved,
    }))
  );
