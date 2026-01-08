/**
 * Diary Panel Component
 *
 * Displays self-reported sleep diary entries for the current file/date.
 * Allows viewing and editing diary data alongside actigraphy markers.
 */

import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Book, Upload, Loader2, Clock, Moon, Sun, Star } from "lucide-react";
import { useSleepScoringStore } from "@/store";
import { diaryApi } from "@/api/client";
import type { DiaryEntryResponse, DiaryEntryCreate } from "@/api/types";

interface DiaryPanelProps {
  /** Whether to show compact mode (less spacing) */
  compact?: boolean;
}

/**
 * Format time string for display (HH:MM)
 */
function formatTimeDisplay(time: string | null | undefined): string {
  if (!time) return "--:--";
  return time;
}

export function DiaryPanel({ compact = false }: DiaryPanelProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  // Get current file and date from store
  const currentFileId = useSleepScoringStore((state) => state.currentFileId);
  const currentDateIndex = useSleepScoringStore((state) => state.currentDateIndex);
  const availableDates = useSleepScoringStore((state) => state.availableDates);
  const currentDate = availableDates[currentDateIndex] ?? null;

  // Local form state for editing
  const [formData, setFormData] = useState<DiaryEntryCreate>({
    bed_time: null,
    wake_time: null,
    lights_out: null,
    got_up: null,
    sleep_quality: null,
    time_to_fall_asleep_minutes: null,
    number_of_awakenings: null,
    notes: null,
  });

  // Fetch diary entry for current file/date
  const { data: diaryEntry, isLoading } = useQuery({
    queryKey: ["diary", currentFileId, currentDate],
    queryFn: () => diaryApi.getDiaryEntry(currentFileId!, currentDate!),
    enabled: !!currentFileId && !!currentDate,
  });

  // Update diary entry mutation
  const updateMutation = useMutation({
    mutationFn: (data: DiaryEntryCreate) =>
      diaryApi.updateDiaryEntry(currentFileId!, currentDate!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["diary", currentFileId, currentDate] });
      setIsEditing(false);
    },
  });

  // Upload diary CSV mutation
  const uploadMutation = useMutation({
    mutationFn: (file: File) => diaryApi.uploadDiaryCsv(currentFileId!, file),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["diary"] });
      setUploadError(null);
      alert(`Imported ${result.entries_imported} entries, skipped ${result.entries_skipped}`);
    },
    onError: (error: Error) => {
      setUploadError(error.message);
    },
  });

  // Handle file upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadMutation.mutate(file);
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Start editing
  const handleStartEdit = () => {
    setFormData({
      bed_time: diaryEntry?.bed_time ?? null,
      wake_time: diaryEntry?.wake_time ?? null,
      lights_out: diaryEntry?.lights_out ?? null,
      got_up: diaryEntry?.got_up ?? null,
      sleep_quality: diaryEntry?.sleep_quality ?? null,
      time_to_fall_asleep_minutes: diaryEntry?.time_to_fall_asleep_minutes ?? null,
      number_of_awakenings: diaryEntry?.number_of_awakenings ?? null,
      notes: diaryEntry?.notes ?? null,
    });
    setIsEditing(true);
  };

  // Save changes
  const handleSave = () => {
    updateMutation.mutate(formData);
  };

  // Cancel editing
  const handleCancel = () => {
    setIsEditing(false);
  };

  if (!currentFileId || !currentDate) {
    return (
      <Card className={compact ? "h-full" : ""}>
        <CardHeader className={compact ? "py-2 px-3" : ""}>
          <CardTitle className={compact ? "text-sm" : "text-base"}>
            <Book className="h-4 w-4 inline mr-2" />
            Sleep Diary
          </CardTitle>
        </CardHeader>
        <CardContent className={compact ? "p-2" : ""}>
          <p className="text-sm text-muted-foreground">Select a file and date to view diary</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={compact ? "h-full flex flex-col" : ""}>
      <CardHeader className={compact ? "py-2 px-3 flex-none" : ""}>
        <div className="flex items-center justify-between">
          <CardTitle className={compact ? "text-sm" : "text-base"}>
            <Book className="h-4 w-4 inline mr-2" />
            Sleep Diary
          </CardTitle>
          <div className="flex items-center gap-1">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              className="hidden"
            />
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadMutation.isPending}
            >
              {uploadMutation.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Upload className="h-3 w-3" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className={compact ? "p-2 flex-1 overflow-y-auto" : ""}>
        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : isEditing ? (
          /* Edit mode */
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="diary-bed-time" className="text-xs">Bed Time</Label>
                <Input
                  id="diary-bed-time"
                  type="time"
                  className="h-7 text-xs"
                  value={formData.bed_time ?? ""}
                  onChange={(e) => setFormData({ ...formData, bed_time: e.target.value || null })}
                />
              </div>
              <div>
                <Label htmlFor="diary-wake-time" className="text-xs">Wake Time</Label>
                <Input
                  id="diary-wake-time"
                  type="time"
                  className="h-7 text-xs"
                  value={formData.wake_time ?? ""}
                  onChange={(e) => setFormData({ ...formData, wake_time: e.target.value || null })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="diary-lights-out" className="text-xs">Lights Out</Label>
                <Input
                  id="diary-lights-out"
                  type="time"
                  className="h-7 text-xs"
                  value={formData.lights_out ?? ""}
                  onChange={(e) => setFormData({ ...formData, lights_out: e.target.value || null })}
                />
              </div>
              <div>
                <Label htmlFor="diary-got-up" className="text-xs">Got Up</Label>
                <Input
                  id="diary-got-up"
                  type="time"
                  className="h-7 text-xs"
                  value={formData.got_up ?? ""}
                  onChange={(e) => setFormData({ ...formData, got_up: e.target.value || null })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="diary-quality" className="text-xs">Quality (1-5)</Label>
                <Input
                  id="diary-quality"
                  type="number"
                  min={1}
                  max={5}
                  className="h-7 text-xs"
                  value={formData.sleep_quality ?? ""}
                  onChange={(e) => setFormData({ ...formData, sleep_quality: e.target.value ? parseInt(e.target.value) : null })}
                />
              </div>
              <div>
                <Label htmlFor="diary-time-to-sleep" className="text-xs">Time to Sleep (min)</Label>
                <Input
                  id="diary-time-to-sleep"
                  type="number"
                  min={0}
                  className="h-7 text-xs"
                  value={formData.time_to_fall_asleep_minutes ?? ""}
                  onChange={(e) => setFormData({ ...formData, time_to_fall_asleep_minutes: e.target.value ? parseInt(e.target.value) : null })}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="diary-notes" className="text-xs">Notes</Label>
              <Input
                id="diary-notes"
                className="h-7 text-xs"
                value={formData.notes ?? ""}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value || null })}
                placeholder="Optional notes..."
              />
            </div>
            <div className="flex gap-2 pt-1">
              <Button size="sm" className="h-7 text-xs flex-1" onClick={handleSave} disabled={updateMutation.isPending}>
                {updateMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Save"}
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs flex-1" onClick={handleCancel}>
                Cancel
              </Button>
            </div>
          </div>
        ) : diaryEntry ? (
          /* View mode with data */
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <div className="flex items-center gap-1">
                <Moon className="h-3 w-3 text-blue-500" />
                <span className="text-muted-foreground">Bed:</span>
                <span className="font-medium">{formatTimeDisplay(diaryEntry.bed_time)}</span>
              </div>
              <div className="flex items-center gap-1">
                <Sun className="h-3 w-3 text-yellow-500" />
                <span className="text-muted-foreground">Wake:</span>
                <span className="font-medium">{formatTimeDisplay(diaryEntry.wake_time)}</span>
              </div>
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3 text-purple-500" />
                <span className="text-muted-foreground">Lights:</span>
                <span className="font-medium">{formatTimeDisplay(diaryEntry.lights_out)}</span>
              </div>
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3 text-green-500" />
                <span className="text-muted-foreground">Up:</span>
                <span className="font-medium">{formatTimeDisplay(diaryEntry.got_up)}</span>
              </div>
            </div>
            {diaryEntry.sleep_quality && (
              <div className="flex items-center gap-1 text-xs">
                <Star className="h-3 w-3 text-amber-500" />
                <span className="text-muted-foreground">Quality:</span>
                <span className="font-medium">{diaryEntry.sleep_quality}/5</span>
              </div>
            )}
            {diaryEntry.notes && (
              <p className="text-xs text-muted-foreground italic truncate" title={diaryEntry.notes}>
                {diaryEntry.notes}
              </p>
            )}
            <Button variant="outline" size="sm" className="h-6 text-xs w-full mt-2" onClick={handleStartEdit}>
              Edit
            </Button>
          </div>
        ) : (
          /* No diary entry */
          <div className="text-center py-2">
            <p className="text-xs text-muted-foreground mb-2">No diary entry for this date</p>
            <Button variant="outline" size="sm" className="h-6 text-xs" onClick={handleStartEdit}>
              Add Entry
            </Button>
          </div>
        )}
        {uploadError && (
          <p className="text-xs text-destructive mt-2">{uploadError}</p>
        )}
      </CardContent>
    </Card>
  );
}
