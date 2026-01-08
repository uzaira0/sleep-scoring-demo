import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Database, Cpu, Clock, Settings, FlaskConical, FileCode, TestTube, Info, Loader2, Save, RotateCcw } from "lucide-react";
import { useSleepScoringStore } from "@/store";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "@/api/client";
import { ALGORITHM_TYPES, SLEEP_DETECTION_RULES } from "@/api/types";

const ALGORITHM_OPTIONS = [
  { value: ALGORITHM_TYPES.SADEH_1994_ACTILIFE, label: "Sadeh (1994) ActiLife - Recommended" },
  { value: ALGORITHM_TYPES.SADEH_1994_ORIGINAL, label: "Sadeh (1994) Original" },
  { value: ALGORITHM_TYPES.COLE_KRIPKE_1992_ACTILIFE, label: "Cole-Kripke (1992) ActiLife" },
  { value: ALGORITHM_TYPES.COLE_KRIPKE_1992_ORIGINAL, label: "Cole-Kripke (1992) Original" },
];

const SLEEP_DETECTION_OPTIONS = [
  { value: SLEEP_DETECTION_RULES.CONSECUTIVE_3S_5S, label: "3-min Onset / 5-min Offset (Default)" },
  { value: SLEEP_DETECTION_RULES.CONSECUTIVE_5S_10S, label: "5-min Onset / 10-min Offset" },
  { value: SLEEP_DETECTION_RULES.TUDOR_LOCKE_2014, label: "Tudor-Locke (2014)" },
];

export function StudySettingsPage() {
  const queryClient = useQueryClient();
  const isAuthenticated = useSleepScoringStore((state) => state.isAuthenticated);

  const {
    currentAlgorithm,
    setCurrentAlgorithm,
    sleepDetectionRule,
    setSleepDetectionRule,
    nightStartHour,
    nightEndHour,
    setNightHours,
  } = useSleepScoringStore();

  // Track if settings have been modified since last save
  const [hasChanges, setHasChanges] = useState(false);

  // Load settings from backend
  const { data: backendSettings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.getSettings,
    enabled: isAuthenticated,
  });

  // Sync backend settings to store on load
  useEffect(() => {
    if (backendSettings) {
      if (backendSettings.default_algorithm) {
        setCurrentAlgorithm(backendSettings.default_algorithm);
      }
      if (backendSettings.sleep_detection_rule) {
        setSleepDetectionRule(backendSettings.sleep_detection_rule as typeof sleepDetectionRule);
      }
      if (backendSettings.night_start_hour && backendSettings.night_end_hour) {
        setNightHours(backendSettings.night_start_hour, backendSettings.night_end_hour);
      }
      setHasChanges(false);
    }
  }, [backendSettings, setCurrentAlgorithm, setSleepDetectionRule, setNightHours]);

  // Save settings mutation
  const saveMutation = useMutation({
    mutationFn: settingsApi.updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setHasChanges(false);
    },
  });

  // Reset settings mutation
  const resetMutation = useMutation({
    mutationFn: settingsApi.resetSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setHasChanges(false);
    },
  });

  // Handlers that track changes
  const handleAlgorithmChange = (value: string) => {
    setCurrentAlgorithm(value);
    setHasChanges(true);
  };

  const handleSleepDetectionChange = (value: string) => {
    setSleepDetectionRule(value as typeof sleepDetectionRule);
    setHasChanges(true);
  };

  const handleNightStartChange = (value: string) => {
    setNightHours(value, nightEndHour);
    setHasChanges(true);
  };

  const handleNightEndChange = (value: string) => {
    setNightHours(nightStartHour, value);
    setHasChanges(true);
  };

  // Save all settings to backend
  const handleSave = () => {
    saveMutation.mutate({
      default_algorithm: currentAlgorithm,
      sleep_detection_rule: sleepDetectionRule,
      night_start_hour: nightStartHour,
      night_end_hour: nightEndHour,
    });
  };

  // Reset to defaults
  const handleReset = () => {
    if (confirm("Reset all settings to defaults?")) {
      resetMutation.mutate();
    }
  };

  // Local state for regex pattern testing
  const [testFilename, setTestFilename] = useState("TECH-001_T1_20240115.csv");
  const [idPattern, setIdPattern] = useState("([A-Z]+-\\d+)");
  const [timepointPattern, setTimepointPattern] = useState("_(T\\d+)_");
  const [groupPattern, setGroupPattern] = useState("^([A-Z]+)-");

  // Parse test results
  const parseTestResults = () => {
    const results: { field: string; pattern: string; match: string | null }[] = [];

    try {
      const idMatch = testFilename.match(new RegExp(idPattern));
      results.push({ field: "Participant ID", pattern: idPattern, match: idMatch?.[1] ?? null });
    } catch {
      results.push({ field: "Participant ID", pattern: idPattern, match: null });
    }

    try {
      const tpMatch = testFilename.match(new RegExp(timepointPattern));
      results.push({ field: "Timepoint", pattern: timepointPattern, match: tpMatch?.[1] ?? null });
    } catch {
      results.push({ field: "Timepoint", pattern: timepointPattern, match: null });
    }

    try {
      const grpMatch = testFilename.match(new RegExp(groupPattern));
      results.push({ field: "Group", pattern: groupPattern, match: grpMatch?.[1] ?? null });
    } catch {
      results.push({ field: "Group", pattern: groupPattern, match: null });
    }

    return results;
  };

  const testResults = parseTestResults();

  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Study Settings</h1>
          <p className="text-muted-foreground">
            Configure study parameters and processing algorithms
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasChanges && (
            <span className="text-sm text-amber-600 dark:text-amber-400">Unsaved changes</span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleReset}
            disabled={resetMutation.isPending}
          >
            {resetMutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <RotateCcw className="h-4 w-4 mr-1" />
            )}
            Reset
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saveMutation.isPending || !hasChanges}
          >
            {saveMutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save
          </Button>
        </div>
      </div>

      {/* Data Paradigm Info - Epoch-based only for now */}
      <Card className="border-green-500/50 bg-green-500/5">
        <CardContent className="py-4">
          <div className="flex items-start gap-3">
            <Database className="h-5 w-5 text-green-600 mt-0.5" />
            <div>
              <div className="font-medium">Data Paradigm: Epoch-Based</div>
              <div className="text-sm text-muted-foreground">
                CSV files with pre-calculated 60-second activity counts. Compatible with ActiGraph, Actiwatch, and MotionWatch CSV exports.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Regex Patterns */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCode className="h-5 w-5" />
            Filename Patterns
          </CardTitle>
          <CardDescription>
            Configure regex patterns to extract participant information from filenames
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="id-pattern">Participant ID Pattern</Label>
              <Input
                id="id-pattern"
                value={idPattern}
                onChange={(e) => setIdPattern(e.target.value)}
                placeholder="([A-Z]+-\d+)"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timepoint-pattern">Timepoint Pattern</Label>
              <Input
                id="timepoint-pattern"
                value={timepointPattern}
                onChange={(e) => setTimepointPattern(e.target.value)}
                placeholder="_(T\d+)_"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="group-pattern">Group Pattern</Label>
              <Input
                id="group-pattern"
                value={groupPattern}
                onChange={(e) => setGroupPattern(e.target.value)}
                placeholder="^([A-Z]+)-"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Live Pattern Testing */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TestTube className="h-5 w-5" />
            Test Patterns
          </CardTitle>
          <CardDescription>
            Test your regex patterns against a sample filename
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="test-filename">Test Filename</Label>
            <Input
              id="test-filename"
              value={testFilename}
              onChange={(e) => setTestFilename(e.target.value)}
              placeholder="TECH-001_T1_20240115.csv"
            />
          </div>
          <div className="rounded-lg border p-4 bg-muted/50">
            <div className="text-sm font-medium mb-2">Extraction Results:</div>
            <div className="space-y-1 text-sm">
              {testResults.map((result) => (
                <div key={result.field} className="flex items-center gap-2">
                  <span className="font-medium w-32">{result.field}:</span>
                  {result.match ? (
                    <span className="text-green-600 dark:text-green-400 font-mono">{result.match}</span>
                  ) : (
                    <span className="text-red-600 dark:text-red-400">No match</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sleep/Wake Algorithm */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            Sleep/Wake Algorithm
          </CardTitle>
          <CardDescription>
            Select the algorithm used to classify sleep and wake epochs
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="algorithm">Algorithm</Label>
            <Select
              id="algorithm"
              value={currentAlgorithm}
              onChange={(e) => handleAlgorithmChange(e.target.value)}
              options={ALGORITHM_OPTIONS}
            />
          </div>
          <div className="rounded-lg border p-3 bg-muted/30 text-sm">
            <div className="flex items-start gap-2">
              <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
              <div>
                {currentAlgorithm.includes("sadeh") ? (
                  <>
                    <strong>Sadeh Algorithm:</strong> Uses Y-axis activity counts with a weighted moving average. The ActiLife variant matches ActiGraph's ActiLife software output.
                  </>
                ) : (
                  <>
                    <strong>Cole-Kripke Algorithm:</strong> Alternative scoring method using different weighting coefficients. The ActiLife variant matches ActiGraph's ActiLife software output.
                  </>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sleep Period Detection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            Sleep Period Detection
          </CardTitle>
          <CardDescription>
            Configure how sleep onset and offset are detected from algorithm results
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="sleep-detection">Detection Rule</Label>
            <Select
              id="sleep-detection"
              value={sleepDetectionRule}
              onChange={(e) => handleSleepDetectionChange(e.target.value)}
              options={SLEEP_DETECTION_OPTIONS}
            />
          </div>
          <div className="rounded-lg border p-3 bg-muted/30 text-sm">
            <div className="flex items-start gap-2">
              <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
              <div>
                {sleepDetectionRule === SLEEP_DETECTION_RULES.CONSECUTIVE_3S_5S && (
                  <>Sleep onset after 3 consecutive minutes of sleep. Sleep offset after 5 consecutive minutes of wake.</>
                )}
                {sleepDetectionRule === SLEEP_DETECTION_RULES.CONSECUTIVE_5S_10S && (
                  <>Sleep onset after 5 consecutive minutes of sleep. Sleep offset after 10 consecutive minutes of wake.</>
                )}
                {sleepDetectionRule === SLEEP_DETECTION_RULES.TUDOR_LOCKE_2014 && (
                  <>Tudor-Locke (2014) algorithm for sleep period detection with validated parameters.</>
                )}
                {![SLEEP_DETECTION_RULES.CONSECUTIVE_3S_5S, SLEEP_DETECTION_RULES.CONSECUTIVE_5S_10S, SLEEP_DETECTION_RULES.TUDOR_LOCKE_2014].includes(sleepDetectionRule) && (
                  <>Select a detection rule above.</>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Night Hours Window */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Night Hours Window
          </CardTitle>
          <CardDescription>
            Define the time window for detecting main sleep periods
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 max-w-md">
            <div className="space-y-2">
              <Label htmlFor="night-start">Night Start</Label>
              <Input
                id="night-start"
                type="time"
                value={nightStartHour}
                onChange={(e) => handleNightStartChange(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="night-end">Night End</Label>
              <Input
                id="night-end"
                type="time"
                value={nightEndHour}
                onChange={(e) => handleNightEndChange(e.target.value)}
              />
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            Main sleep periods are expected to start within this window. Used for automatic sleep detection.
          </p>
        </CardContent>
      </Card>

      {/* Nonwear Detection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Nonwear Detection
          </CardTitle>
          <CardDescription>
            Algorithm for detecting device non-wear periods
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border p-3 bg-muted/30 text-sm">
            <div className="flex items-start gap-2">
              <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
              <div>
                <strong>Choi Algorithm (2011):</strong> Uses 90-minute window with 2-minute spike tolerance. Standard algorithm for epoch-based actigraphy data.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
