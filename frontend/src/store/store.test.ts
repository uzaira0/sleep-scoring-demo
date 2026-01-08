/**
 * Tests for the Zustand store.
 *
 * Uses Bun's built-in test runner.
 */

import { describe, it, expect, beforeEach } from "bun:test";
import { useSleepScoringStore } from "./index";
import { MARKER_TYPES } from "@/api/types";

describe("SleepScoringStore", () => {
  // Reset store before each test
  beforeEach(() => {
    useSleepScoringStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      currentFileId: null,
      currentFilename: null,
      currentDateIndex: 0,
      availableDates: [],
      availableFiles: [],
      timestamps: [],
      axisX: [],
      axisY: [],
      axisZ: [],
      vectorMagnitude: [],
      algorithmResults: null,
      isLoading: false,
      sleepMarkers: [],
      nonwearMarkers: [],
      isDirty: false,
      selectedPeriodIndex: null,
      preferredDisplayColumn: "axis_y",
      viewModeHours: 24,
      currentAlgorithm: "sadeh_1994_actilife",
    });
  });

  describe("Auth state", () => {
    it("should start with unauthenticated state", () => {
      const state = useSleepScoringStore.getState();

      expect(state.isAuthenticated).toBe(false);
      expect(state.accessToken).toBeNull();
      expect(state.user).toBeNull();
    });

    it("should set auth state correctly", () => {
      const { setAuth } = useSleepScoringStore.getState();

      setAuth("test-token", "refresh-token", {
        id: 1,
        email: "test@example.com",
        username: "testuser",
        role: "admin",
      });

      const state = useSleepScoringStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.accessToken).toBe("test-token");
      expect(state.user?.username).toBe("testuser");
    });

    it("should clear auth state correctly", () => {
      const { setAuth, clearAuth } = useSleepScoringStore.getState();

      // First set auth
      setAuth("test-token", "refresh-token", {
        id: 1,
        email: "test@example.com",
        username: "testuser",
        role: "admin",
      });

      // Then clear it
      clearAuth();

      const state = useSleepScoringStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.accessToken).toBeNull();
      expect(state.user).toBeNull();
    });
  });

  describe("File state", () => {
    it("should set current file correctly", () => {
      const { setCurrentFile } = useSleepScoringStore.getState();

      setCurrentFile(123, "test-file.csv");

      const state = useSleepScoringStore.getState();
      expect(state.currentFileId).toBe(123);
      expect(state.currentFilename).toBe("test-file.csv");
      // Should reset date index when file changes
      expect(state.currentDateIndex).toBe(0);
    });

    it("should set available files correctly", () => {
      const { setAvailableFiles } = useSleepScoringStore.getState();

      const files = [
        { id: 1, filename: "file1.csv", status: "ready", rowCount: 100 },
        { id: 2, filename: "file2.csv", status: "ready", rowCount: 200 },
      ];

      setAvailableFiles(files);

      const state = useSleepScoringStore.getState();
      expect(state.availableFiles).toHaveLength(2);
      expect(state.availableFiles[0].filename).toBe("file1.csv");
    });

    it("should set available dates correctly", () => {
      const { setAvailableDates } = useSleepScoringStore.getState();

      setAvailableDates(["2024-01-01", "2024-01-02", "2024-01-03"]);

      const state = useSleepScoringStore.getState();
      expect(state.availableDates).toHaveLength(3);
      expect(state.availableDates[0]).toBe("2024-01-01");
    });
  });

  describe("Date navigation", () => {
    beforeEach(() => {
      const { setAvailableDates } = useSleepScoringStore.getState();
      setAvailableDates(["2024-01-01", "2024-01-02", "2024-01-03"]);
    });

    it("should navigate forward", () => {
      const { navigateDate } = useSleepScoringStore.getState();

      navigateDate(1);

      const state = useSleepScoringStore.getState();
      expect(state.currentDateIndex).toBe(1);
    });

    it("should navigate backward", () => {
      // Start at index 2
      useSleepScoringStore.setState({ currentDateIndex: 2 });

      const { navigateDate } = useSleepScoringStore.getState();
      navigateDate(-1);

      const state = useSleepScoringStore.getState();
      expect(state.currentDateIndex).toBe(1);
    });

    it("should not navigate past end", () => {
      useSleepScoringStore.setState({ currentDateIndex: 2 });

      const { navigateDate } = useSleepScoringStore.getState();
      navigateDate(1);

      const state = useSleepScoringStore.getState();
      expect(state.currentDateIndex).toBe(2); // Should stay at 2
    });

    it("should not navigate before start", () => {
      const { navigateDate } = useSleepScoringStore.getState();
      navigateDate(-1);

      const state = useSleepScoringStore.getState();
      expect(state.currentDateIndex).toBe(0); // Should stay at 0
    });
  });

  describe("Activity data state", () => {
    it("should set activity data correctly", () => {
      const { setActivityData } = useSleepScoringStore.getState();

      setActivityData({
        timestamps: [1000, 2000, 3000],
        axisX: [10, 20, 30],
        axisY: [15, 25, 35],
        axisZ: [5, 10, 15],
        vectorMagnitude: [100, 200, 300],
        algorithmResults: [0, 1, 0],
      });

      const state = useSleepScoringStore.getState();
      expect(state.timestamps).toHaveLength(3);
      expect(state.axisY[1]).toBe(25);
      expect(state.algorithmResults).toEqual([0, 1, 0]);
      expect(state.isLoading).toBe(false);
    });

    it("should clear activity data correctly", () => {
      // First set some data
      const { setActivityData, clearActivityData } =
        useSleepScoringStore.getState();

      setActivityData({
        timestamps: [1000, 2000],
        axisX: [10, 20],
        axisY: [15, 25],
        axisZ: [5, 10],
        vectorMagnitude: [100, 200],
      });

      clearActivityData();

      const state = useSleepScoringStore.getState();
      expect(state.timestamps).toHaveLength(0);
      expect(state.axisY).toHaveLength(0);
    });

    it("should set loading state correctly", () => {
      const { setLoading } = useSleepScoringStore.getState();

      setLoading(true);
      expect(useSleepScoringStore.getState().isLoading).toBe(true);

      setLoading(false);
      expect(useSleepScoringStore.getState().isLoading).toBe(false);
    });
  });

  describe("Marker state", () => {
    it("should set sleep markers and mark dirty", () => {
      const { setSleepMarkers } = useSleepScoringStore.getState();

      const markers = [
        {
          onsetTimestamp: 1000,
          offsetTimestamp: 2000,
          markerIndex: 0,
          markerType: MARKER_TYPES.MAIN_SLEEP,
        },
      ];

      setSleepMarkers(markers);

      const state = useSleepScoringStore.getState();
      expect(state.sleepMarkers).toHaveLength(1);
      expect(state.isDirty).toBe(true);
    });

    it("should set nonwear markers and mark dirty", () => {
      const { setNonwearMarkers } = useSleepScoringStore.getState();

      const markers = [
        {
          startTimestamp: 1000,
          endTimestamp: 2000,
          markerIndex: 0,
        },
      ];

      setNonwearMarkers(markers);

      const state = useSleepScoringStore.getState();
      expect(state.nonwearMarkers).toHaveLength(1);
      expect(state.isDirty).toBe(true);
    });

    it("should set selected period index", () => {
      const { setSelectedPeriod } = useSleepScoringStore.getState();

      setSelectedPeriod(2);
      expect(useSleepScoringStore.getState().selectedPeriodIndex).toBe(2);

      setSelectedPeriod(null);
      expect(useSleepScoringStore.getState().selectedPeriodIndex).toBeNull();
    });
  });

  describe("Preferences state", () => {
    it("should set preferred display column", () => {
      const { setPreferredDisplayColumn } = useSleepScoringStore.getState();

      setPreferredDisplayColumn("vector_magnitude");
      expect(useSleepScoringStore.getState().preferredDisplayColumn).toBe(
        "vector_magnitude"
      );
    });

    it("should set view mode hours", () => {
      const { setViewModeHours } = useSleepScoringStore.getState();

      setViewModeHours(48);
      expect(useSleepScoringStore.getState().viewModeHours).toBe(48);
    });

    it("should set current algorithm", () => {
      const { setCurrentAlgorithm } = useSleepScoringStore.getState();

      setCurrentAlgorithm("cole_kripke_1992");
      expect(useSleepScoringStore.getState().currentAlgorithm).toBe(
        "cole_kripke_1992"
      );
    });
  });
});
