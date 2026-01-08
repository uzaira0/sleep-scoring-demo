/**
 * Export page for generating CSV exports of sleep scoring data.
 */

import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useSleepScoringStore } from "@/store";
import { fetchWithAuth } from "@/api/client";

interface ExportColumnInfo {
  name: string;
  category: string;
  description: string | null;
  data_type: string;
  is_default: boolean;
}

interface ExportColumnCategory {
  name: string;
  columns: string[];
}

interface ExportColumnsResponse {
  columns: ExportColumnInfo[];
  categories: ExportColumnCategory[];
}

interface FileInfo {
  id: number;
  filename: string;
  participant_id: string | null;
  status: string;
}

interface FileListResponse {
  files: FileInfo[];
  total: number;
}

interface ExportRequest {
  file_ids: number[];
  columns: string[] | null;
  include_header: boolean;
  include_metadata: boolean;
}

export function ExportPage() {
  const navigate = useNavigate();
  const token = useSleepScoringStore((state) => state.accessToken);

  // Selected files and columns state
  const [selectedFileIds, setSelectedFileIds] = useState<number[]>([]);
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [includeHeader, setIncludeHeader] = useState(true);
  const [includeMetadata, setIncludeMetadata] = useState(false);

  // Fetch available files
  const { data: filesData, isLoading: filesLoading } = useQuery({
    queryKey: ["files"],
    queryFn: () => fetchWithAuth<FileListResponse>("/api/v1/files"),
    enabled: !!token,
  });

  // Fetch available columns
  const { data: columnsData, isLoading: columnsLoading } = useQuery({
    queryKey: ["export-columns"],
    queryFn: () => fetchWithAuth<ExportColumnsResponse>("/api/v1/export/columns"),
    enabled: !!token,
  });

  // Initialize selected columns with defaults when data loads
  useEffect(() => {
    if (columnsData?.columns) {
      const defaultColumns = columnsData.columns
        .filter((col) => col.is_default)
        .map((col) => col.name);
      setSelectedColumns(defaultColumns);
    }
  }, [columnsData]);

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: async (request: ExportRequest) => {
      const response = await fetch("/api/v1/export/csv/download", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error("Export failed");
      }

      // Get filename from Content-Disposition header
      const disposition = response.headers.get("Content-Disposition");
      let filename = "export.csv";
      if (disposition) {
        const match = disposition.match(/filename="(.+)"/);
        if (match) {
          filename = match[1];
        }
      }

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      return { success: true, filename };
    },
  });

  // Handle file selection toggle
  const toggleFileSelection = (fileId: number) => {
    setSelectedFileIds((prev) =>
      prev.includes(fileId) ? prev.filter((id) => id !== fileId) : [...prev, fileId]
    );
  };

  // Handle select all files
  const selectAllFiles = () => {
    if (filesData?.files) {
      setSelectedFileIds(filesData.files.map((f) => f.id));
    }
  };

  // Handle clear all files
  const clearAllFiles = () => {
    setSelectedFileIds([]);
  };

  // Handle column selection toggle
  const toggleColumnSelection = (columnName: string) => {
    setSelectedColumns((prev) =>
      prev.includes(columnName)
        ? prev.filter((name) => name !== columnName)
        : [...prev, columnName]
    );
  };

  // Handle category selection (toggle all columns in category)
  const toggleCategorySelection = (category: ExportColumnCategory) => {
    const allSelected = category.columns.every((col) => selectedColumns.includes(col));
    if (allSelected) {
      // Deselect all in category
      setSelectedColumns((prev) => prev.filter((col) => !category.columns.includes(col)));
    } else {
      // Select all in category
      setSelectedColumns((prev) => [...new Set([...prev, ...category.columns])]);
    }
  };

  // Handle export
  const handleExport = () => {
    if (selectedFileIds.length === 0) {
      alert("Please select at least one file to export");
      return;
    }

    exportMutation.mutate({
      file_ids: selectedFileIds,
      columns: selectedColumns.length > 0 ? selectedColumns : null,
      include_header: includeHeader,
      include_metadata: includeMetadata,
    });
  };

  // Redirect if not logged in
  if (!token) {
    navigate("/login");
    return null;
  }

  const isLoading = filesLoading || columnsLoading;

  return (
    <div className="container mx-auto py-6 px-4 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Export Data</h1>
          <p className="text-muted-foreground">
            Generate CSV exports of sleep scoring data
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate("/scoring")}>
          Back to Scoring
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-muted-foreground">Loading...</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* File Selection */}
          <Card>
            <CardHeader>
              <CardTitle>Select Files</CardTitle>
              <CardDescription>
                Choose which files to include in the export
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 mb-4">
                <Button variant="outline" size="sm" onClick={selectAllFiles}>
                  Select All
                </Button>
                <Button variant="outline" size="sm" onClick={clearAllFiles}>
                  Clear All
                </Button>
              </div>
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                {filesData?.files.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center space-x-2 p-2 hover:bg-muted rounded"
                  >
                    <Checkbox
                      id={`file-${file.id}`}
                      checked={selectedFileIds.includes(file.id)}
                      onCheckedChange={() => toggleFileSelection(file.id)}
                    />
                    <Label
                      htmlFor={`file-${file.id}`}
                      className="flex-1 cursor-pointer"
                    >
                      <span className="font-medium">{file.filename}</span>
                      {file.participant_id && (
                        <span className="text-muted-foreground ml-2">
                          ({file.participant_id})
                        </span>
                      )}
                    </Label>
                  </div>
                ))}
                {(!filesData?.files || filesData.files.length === 0) && (
                  <div className="text-muted-foreground py-4 text-center">
                    No files available
                  </div>
                )}
              </div>
              <div className="mt-4 text-sm text-muted-foreground">
                {selectedFileIds.length} of {filesData?.files.length || 0} files
                selected
              </div>
            </CardContent>
          </Card>

          {/* Column Selection */}
          <Card>
            <CardHeader>
              <CardTitle>Select Columns</CardTitle>
              <CardDescription>
                Choose which data columns to include
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 max-h-[400px] overflow-y-auto">
                {columnsData?.categories.map((category) => {
                  const allSelected = category.columns.every((col) =>
                    selectedColumns.includes(col)
                  );
                  const someSelected = category.columns.some((col) =>
                    selectedColumns.includes(col)
                  );

                  return (
                    <div key={category.name} className="space-y-2">
                      <div
                        className="flex items-center space-x-2 cursor-pointer"
                        onClick={() => toggleCategorySelection(category)}
                      >
                        <Checkbox
                          checked={allSelected}
                          // @ts-ignore - indeterminate is valid but not in types
                          indeterminate={someSelected && !allSelected}
                          onCheckedChange={() =>
                            toggleCategorySelection(category)
                          }
                        />
                        <span className="font-semibold text-sm">
                          {category.name}
                        </span>
                      </div>
                      <div className="ml-6 grid grid-cols-1 gap-1">
                        {category.columns.map((columnName) => {
                          const column = columnsData.columns.find(
                            (c) => c.name === columnName
                          );
                          return (
                            <div
                              key={columnName}
                              className="flex items-center space-x-2"
                            >
                              <Checkbox
                                id={`col-${columnName}`}
                                checked={selectedColumns.includes(columnName)}
                                onCheckedChange={() =>
                                  toggleColumnSelection(columnName)
                                }
                              />
                              <Label
                                htmlFor={`col-${columnName}`}
                                className="text-sm cursor-pointer"
                                title={column?.description || ""}
                              >
                                {columnName}
                              </Label>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-4 text-sm text-muted-foreground">
                {selectedColumns.length} columns selected
              </div>
            </CardContent>
          </Card>

          {/* Export Options */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Export Options</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-6">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="include-header"
                    checked={includeHeader}
                    onCheckedChange={(checked) =>
                      setIncludeHeader(checked === true)
                    }
                  />
                  <Label htmlFor="include-header">Include header row</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="include-metadata"
                    checked={includeMetadata}
                    onCheckedChange={(checked) =>
                      setIncludeMetadata(checked === true)
                    }
                  />
                  <Label htmlFor="include-metadata">
                    Include metadata comments
                  </Label>
                </div>
              </div>

              <div className="mt-6 flex justify-end">
                <Button
                  onClick={handleExport}
                  disabled={
                    selectedFileIds.length === 0 || exportMutation.isPending
                  }
                  size="lg"
                >
                  {exportMutation.isPending ? "Exporting..." : "Download CSV"}
                </Button>
              </div>

              {exportMutation.isSuccess && (
                <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 rounded">
                  Export completed successfully!
                </div>
              )}

              {exportMutation.isError && (
                <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded">
                  Export failed. Please try again.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
