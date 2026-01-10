import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Database, FileText, Trash2, RefreshCw, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSleepScoringStore } from "@/store";

const DEVICE_PRESET_OPTIONS = [
  { value: "actigraph", label: "ActiGraph (ActiLife CSV Export)" },
  { value: "actiwatch", label: "Actiwatch" },
  { value: "motionwatch", label: "MotionWatch" },
  { value: "geneactiv", label: "GENEActiv" },
  { value: "generic", label: "Generic CSV" },
];

export function DataSettingsPage() {
  const {
    devicePreset,
    setDevicePreset,
    epochLengthSeconds,
    setEpochLengthSeconds,
    skipRows,
    setSkipRows,
    sleepMarkers,
    nonwearMarkers,
    setSleepMarkers,
    setNonwearMarkers,
    currentFileId,
  } = useSleepScoringStore();

  const handleClearSleepMarkers = () => {
    if (confirm("Are you sure you want to clear all sleep markers for the current file?")) {
      setSleepMarkers([]);
    }
  };

  const handleClearNonwearMarkers = () => {
    if (confirm("Are you sure you want to clear all nonwear markers for the current file?")) {
      setNonwearMarkers([]);
    }
  };

  const handleClearAllMarkers = () => {
    if (confirm("Are you sure you want to clear ALL markers for the current file?")) {
      setSleepMarkers([]);
      setNonwearMarkers([]);
    }
  };

  const handleAutoDetect = () => {
    // Auto-detect settings based on device preset
    switch (devicePreset) {
      case "actigraph":
        setEpochLengthSeconds(60);
        setSkipRows(10);
        break;
      case "actiwatch":
        setEpochLengthSeconds(60);
        setSkipRows(7);
        break;
      case "motionwatch":
        setEpochLengthSeconds(60);
        setSkipRows(8);
        break;
      case "geneactiv":
        setEpochLengthSeconds(60);
        setSkipRows(100);
        break;
      default:
        setEpochLengthSeconds(60);
        setSkipRows(0);
    }
  };

  const hasFile = currentFileId !== null;
  const hasSleepMarkers = sleepMarkers.length > 0;
  const hasNonwearMarkers = nonwearMarkers.length > 0;
  const hasAnyMarkers = hasSleepMarkers || hasNonwearMarkers;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Data Settings</h1>
        <p className="text-muted-foreground">
          Configure CSV import settings and file parsing options
        </p>
      </div>

      {/* Data Paradigm Info */}
      <Card className="border-green-500/50 bg-green-500/5">
        <CardContent className="py-4">
          <div className="flex items-start gap-3">
            <Database className="h-5 w-5 text-green-600 mt-0.5" />
            <div>
              <div className="font-medium">Data Source: Epoch CSV Files</div>
              <div className="text-sm text-muted-foreground">
                Pre-processed CSV files with 60-second epoch activity counts. Standard format from ActiLife and similar software.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* CSV Import Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            CSV Import Configuration
          </CardTitle>
          <CardDescription>
            Configure how CSV files are parsed during import
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Device Preset */}
          <div className="space-y-2">
            <Label htmlFor="device-preset">Device Preset</Label>
            <div className="flex gap-2">
              <Select
                id="device-preset"
                value={devicePreset}
                onChange={(e) => {
                  setDevicePreset(e.target.value as "actigraph" | "actiwatch" | "motionwatch" | "geneactiv" | "generic");
                  // Auto-apply settings for the preset
                  setTimeout(handleAutoDetect, 0);
                }}
                options={DEVICE_PRESET_OPTIONS}
                className="flex-1"
              />
            </div>
            <p className="text-sm text-muted-foreground">
              Select your device type to auto-configure epoch length and header rows.
            </p>
          </div>

          {/* Epoch Length and Skip Rows */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="epoch-length">Epoch Length (seconds)</Label>
              <div className="flex gap-2">
                <Input
                  id="epoch-length"
                  type="number"
                  min={1}
                  max={300}
                  value={epochLengthSeconds}
                  onChange={(e) => setEpochLengthSeconds(Number(e.target.value))}
                  className="flex-1"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="skip-rows">Skip Header Rows</Label>
              <div className="flex gap-2">
                <Input
                  id="skip-rows"
                  type="number"
                  min={0}
                  max={200}
                  value={skipRows}
                  onChange={(e) => setSkipRows(Number(e.target.value))}
                  className="flex-1"
                />
              </div>
            </div>
          </div>

          {/* Auto-detect button */}
          <div className="flex justify-end">
            <Button variant="outline" onClick={handleAutoDetect}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Apply Preset Defaults
            </Button>
          </div>

          {/* Info box */}
          <div className="rounded-lg border p-3 bg-muted/30 text-sm">
            <div className="flex items-start gap-2">
              <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
              <div>
                <strong>ActiGraph CSV:</strong> 60-second epochs, 10 header rows.
                <strong className="ml-3">Actiwatch:</strong> 60-second epochs, 7 header rows.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Data Management / Clear */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trash2 className="h-5 w-5" />
            Data Management
          </CardTitle>
          <CardDescription>
            Clear markers for the current file
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <Button
              variant="outline"
              className="h-auto py-3 flex flex-col items-center gap-1"
              disabled={!hasFile || !hasSleepMarkers}
              onClick={handleClearSleepMarkers}
            >
              <span className="font-medium">Clear Sleep Markers</span>
              <span className="text-xs text-muted-foreground">
                {hasSleepMarkers ? `${sleepMarkers.length} markers` : "No markers"}
              </span>
            </Button>
            <Button
              variant="outline"
              className="h-auto py-3 flex flex-col items-center gap-1"
              disabled={!hasFile || !hasNonwearMarkers}
              onClick={handleClearNonwearMarkers}
            >
              <span className="font-medium">Clear Nonwear Markers</span>
              <span className="text-xs text-muted-foreground">
                {hasNonwearMarkers ? `${nonwearMarkers.length} markers` : "No markers"}
              </span>
            </Button>
            <Button
              variant="outline"
              className="h-auto py-3 flex flex-col items-center gap-1"
              disabled={!hasFile || !hasAnyMarkers}
              onClick={handleClearAllMarkers}
            >
              <span className="font-medium">Clear All Markers</span>
              <span className="text-xs text-muted-foreground">
                {hasAnyMarkers ? "Clear everything" : "No data"}
              </span>
            </Button>
          </div>
          {!hasFile && (
            <p className="text-sm text-muted-foreground">
              Select a file on the Scoring page to enable data management options.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
