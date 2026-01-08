// Auto-generated from OpenAPI schema
// Do not edit manually

export const schema = {
  "openapi": "3.1.0",
  "info": {
    "title": "Sleep Scoring Web",
    "description": "Web API for sleep scoring and activity data analysis",
    "version": "0.1.0"
  },
  "paths": {
    "/health": {
      "get": {
        "summary": "Health Check",
        "description": "Health check endpoint.",
        "operationId": "health_check_health_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "additionalProperties": {
                    "type": "string"
                  },
                  "type": "object",
                  "title": "Response Health Check Health Get"
                }
              }
            }
          }
        }
      }
    },
    "/": {
      "get": {
        "summary": "Root",
        "description": "Root endpoint with API info.",
        "operationId": "root__get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "additionalProperties": {
                    "type": "string"
                  },
                  "type": "object",
                  "title": "Response Root  Get"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/register": {
      "post": {
        "tags": [
          "auth"
        ],
        "summary": "Register",
        "description": "Register a new user.",
        "operationId": "register_api_v1_auth_register_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/UserCreate"
              }
            }
          },
          "required": true
        },
        "responses": {
          "201": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/UserRead"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/login": {
      "post": {
        "tags": [
          "auth"
        ],
        "summary": "Login",
        "description": "Login and get JWT tokens.",
        "operationId": "login_api_v1_auth_login_post",
        "requestBody": {
          "content": {
            "application/x-www-form-urlencoded": {
              "schema": {
                "$ref": "#/components/schemas/Body_login_api_v1_auth_login_post"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/Token"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/refresh": {
      "post": {
        "tags": [
          "auth"
        ],
        "summary": "Refresh Token",
        "description": "Refresh access token using refresh token.",
        "operationId": "refresh_token_api_v1_auth_refresh_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/TokenRefresh"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/Token"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/me": {
      "get": {
        "tags": [
          "auth"
        ],
        "summary": "Get Me",
        "description": "Get current user information.",
        "operationId": "get_me_api_v1_auth_me_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/UserRead"
                }
              }
            }
          }
        },
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ]
      }
    },
    "/api/v1/files/upload": {
      "post": {
        "tags": [
          "files"
        ],
        "summary": "Upload File",
        "description": "Upload a CSV file for processing.\n\nThe file will be parsed, validated, and stored in the database.\nActivity data will be extracted and made available for analysis.",
        "operationId": "upload_file_api_v1_files_upload_post",
        "requestBody": {
          "content": {
            "multipart/form-data": {
              "schema": {
                "$ref": "#/components/schemas/Body_upload_file_api_v1_files_upload_post"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/FileUploadResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        },
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ]
      }
    },
    "/api/v1/files": {
      "get": {
        "tags": [
          "files"
        ],
        "summary": "List Files",
        "description": "List all uploaded files.",
        "operationId": "list_files_api_v1_files_get",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "skip",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "default": 0,
              "title": "Skip"
            }
          },
          {
            "name": "limit",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "default": 100,
              "title": "Limit"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/FileListResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      },
      "delete": {
        "tags": [
          "files"
        ],
        "summary": "Delete All Files",
        "description": "Delete all files from the database (admin only).\n\nOptionally filter by status (e.g., 'failed' to delete only failed files).",
        "operationId": "delete_all_files_api_v1_files_delete",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "status_filter",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "title": "Status Filter"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "additionalProperties": true,
                  "title": "Response Delete All Files Api V1 Files Delete"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/files/{file_id}": {
      "get": {
        "tags": [
          "files"
        ],
        "summary": "Get File",
        "description": "Get file metadata by ID.",
        "operationId": "get_file_api_v1_files__file_id__get",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/FileInfo"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      },
      "delete": {
        "tags": [
          "files"
        ],
        "summary": "Delete File",
        "description": "Delete a file and its associated data.",
        "operationId": "delete_file_api_v1_files__file_id__delete",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          }
        ],
        "responses": {
          "204": {
            "description": "Successful Response"
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/files/{file_id}/dates": {
      "get": {
        "tags": [
          "files"
        ],
        "summary": "Get File Dates",
        "description": "Get available dates for a file.",
        "operationId": "get_file_dates_api_v1_files__file_id__dates_get",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "array",
                  "items": {
                    "type": "string"
                  },
                  "title": "Response Get File Dates Api V1 Files  File Id  Dates Get"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/files/scan": {
      "post": {
        "tags": [
          "files"
        ],
        "summary": "Scan Data Directory",
        "description": "Start a background scan of the data directory for CSV files.\n\nOnly admins can trigger a scan. Files already in the database are skipped.\nReturns immediately with scan status - poll GET /scan/status for progress.",
        "operationId": "scan_data_directory_api_v1_files_scan_post",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "additionalProperties": true,
                  "type": "object",
                  "title": "Response Scan Data Directory Api V1 Files Scan Post"
                }
              }
            }
          }
        },
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ]
      }
    },
    "/api/v1/files/scan/status": {
      "get": {
        "tags": [
          "files"
        ],
        "summary": "Get Scan Status",
        "description": "Get the current status of the background file scan.\n\nPoll this endpoint to track import progress.",
        "operationId": "get_scan_status_api_v1_files_scan_status_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "additionalProperties": true,
                  "type": "object",
                  "title": "Response Get Scan Status Api V1 Files Scan Status Get"
                }
              }
            }
          }
        },
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ]
      }
    },
    "/api/v1/files/watcher/status": {
      "get": {
        "tags": [
          "files"
        ],
        "summary": "Get Watcher Status",
        "description": "Get the current status of the automatic file watcher.\n\nThe file watcher monitors the data directory for new CSV files\nand automatically ingests them into the database.",
        "operationId": "get_watcher_status_api_v1_files_watcher_status_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "additionalProperties": true,
                  "type": "object",
                  "title": "Response Get Watcher Status Api V1 Files Watcher Status Get"
                }
              }
            }
          }
        },
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ]
      }
    },
    "/api/v1/activity/{file_id}/{analysis_date}": {
      "get": {
        "tags": [
          "activity"
        ],
        "summary": "Get Activity Data",
        "description": "Get activity data for a specific file and date.\n\nReturns data in columnar format for efficient transfer.\nThe view window starts from analysis_date at 12:00 (noon) and extends for view_hours.",
        "operationId": "get_activity_data_api_v1_activity__file_id___analysis_date__get",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          },
          {
            "name": "analysis_date",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "format": "date",
              "title": "Analysis Date"
            }
          },
          {
            "name": "view_hours",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "maximum": 48,
              "minimum": 12,
              "description": "Hours of data to return (12-48)",
              "default": 24,
              "title": "View Hours"
            },
            "description": "Hours of data to return (12-48)"
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ActivityDataResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/activity/{file_id}/{analysis_date}/score": {
      "get": {
        "tags": [
          "activity"
        ],
        "summary": "Get Activity Data With Scoring",
        "description": "Get activity data with sleep scoring algorithm results.\n\nReturns data with:\n- Sleep scoring results (1=sleep, 0=wake)\n- Choi nonwear detection results (1=nonwear, 0=wear)\n\nAvailable algorithms:\n- sadeh_1994_actilife (default): Sadeh 1994 with ActiLife scaling\n- sadeh_1994_original: Sadeh 1994 original paper version\n- cole_kripke_1992_actilife: Cole-Kripke 1992 with ActiLife scaling\n- cole_kripke_1992_original: Cole-Kripke 1992 original paper version",
        "operationId": "get_activity_data_with_scoring_api_v1_activity__file_id___analysis_date__score_get",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          },
          {
            "name": "analysis_date",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "format": "date",
              "title": "Analysis Date"
            }
          },
          {
            "name": "view_hours",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "maximum": 48,
              "minimum": 12,
              "default": 24,
              "title": "View Hours"
            }
          },
          {
            "name": "algorithm",
            "in": "query",
            "required": false,
            "schema": {
              "type": "string",
              "description": "Sleep scoring algorithm to use",
              "default": "sadeh_1994_actilife",
              "title": "Algorithm"
            },
            "description": "Sleep scoring algorithm to use"
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ActivityDataResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/activity/{file_id}/{analysis_date}/sadeh": {
      "get": {
        "tags": [
          "activity"
        ],
        "summary": "Get Activity Data With Sadeh",
        "description": "Get activity data with Sadeh algorithm results.\n\nDEPRECATED: Use /{file_id}/{analysis_date}/score?algorithm=sadeh_1994_actilife instead.",
        "operationId": "get_activity_data_with_sadeh_api_v1_activity__file_id___analysis_date__sadeh_get",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          },
          {
            "name": "analysis_date",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "format": "date",
              "title": "Analysis Date"
            }
          },
          {
            "name": "view_hours",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "maximum": 48,
              "minimum": 12,
              "default": 24,
              "title": "View Hours"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ActivityDataResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/markers/{file_id}/{analysis_date}": {
      "get": {
        "tags": [
          "markers"
        ],
        "summary": "Get Markers",
        "description": "Get all markers for a specific file and date.\n\nReturns sleep markers, nonwear markers, and calculated metrics.\nOptionally includes algorithm results for overlay display.",
        "operationId": "get_markers_api_v1_markers__file_id___analysis_date__get",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          },
          {
            "name": "analysis_date",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "format": "date",
              "title": "Analysis Date"
            }
          },
          {
            "name": "include_algorithm",
            "in": "query",
            "required": false,
            "schema": {
              "type": "boolean",
              "description": "Include Sadeh algorithm results",
              "default": true,
              "title": "Include Algorithm"
            },
            "description": "Include Sadeh algorithm results"
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/MarkersWithMetricsResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      },
      "put": {
        "tags": [
          "markers"
        ],
        "summary": "Save Markers",
        "description": "Save markers for a specific file and date.\n\nReplaces all existing markers for this file/date with the new ones.\nTriggers background calculation of sleep metrics.",
        "operationId": "save_markers_api_v1_markers__file_id___analysis_date__put",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          },
          {
            "name": "analysis_date",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "format": "date",
              "title": "Analysis Date"
            }
          }
        ],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/MarkerUpdateRequest"
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/SaveStatusResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/markers/{file_id}/{analysis_date}/{period_index}": {
      "delete": {
        "tags": [
          "markers"
        ],
        "summary": "Delete Marker",
        "description": "Delete a specific marker period.",
        "operationId": "delete_marker_api_v1_markers__file_id___analysis_date___period_index__delete",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          },
          {
            "name": "analysis_date",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "format": "date",
              "title": "Analysis Date"
            }
          },
          {
            "name": "period_index",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "Period Index"
            }
          },
          {
            "name": "marker_category",
            "in": "query",
            "required": false,
            "schema": {
              "$ref": "#/components/schemas/MarkerCategory",
              "default": "sleep"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "additionalProperties": true,
                  "title": "Response Delete Marker Api V1 Markers  File Id   Analysis Date   Period Index  Delete"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/markers/{file_id}/{analysis_date}/table/{period_index}": {
      "get": {
        "tags": [
          "markers"
        ],
        "summary": "Get Onset Offset Data",
        "description": "Get activity data around a marker for onset/offset tables.\n\nReturns data points within window_minutes of the onset and offset timestamps.",
        "operationId": "get_onset_offset_data_api_v1_markers__file_id___analysis_date__table__period_index__get",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "File Id"
            }
          },
          {
            "name": "analysis_date",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "format": "date",
              "title": "Analysis Date"
            }
          },
          {
            "name": "period_index",
            "in": "path",
            "required": true,
            "schema": {
              "type": "integer",
              "title": "Period Index"
            }
          },
          {
            "name": "window_minutes",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "maximum": 60,
              "minimum": 5,
              "default": 30,
              "title": "Window Minutes"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/OnsetOffsetTableResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/export/columns": {
      "get": {
        "tags": [
          "export"
        ],
        "summary": "Get Export Columns",
        "description": "Get list of available export columns.\n\nReturns all available columns with their metadata, grouped by category.",
        "operationId": "get_export_columns_api_v1_export_columns_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ExportColumnsResponse"
                }
              }
            }
          }
        },
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ]
      }
    },
    "/api/v1/export/csv": {
      "post": {
        "tags": [
          "export"
        ],
        "summary": "Generate Csv Export",
        "description": "Generate CSV export for specified files.\n\nReturns metadata about the export. Use /csv/download to get the actual file.",
        "operationId": "generate_csv_export_api_v1_export_csv_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ExportRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ExportResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        },
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ]
      }
    },
    "/api/v1/export/csv/download": {
      "post": {
        "tags": [
          "export"
        ],
        "summary": "Download Csv Export",
        "description": "Generate and download CSV export.\n\nReturns the CSV file directly as a download.",
        "operationId": "download_csv_export_api_v1_export_csv_download_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ExportRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        },
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ]
      }
    },
    "/api/v1/export/csv/quick": {
      "get": {
        "tags": [
          "export"
        ],
        "summary": "Quick Export",
        "description": "Quick export endpoint for simple GET requests.\n\nUses default columns and returns CSV directly.",
        "operationId": "quick_export_api_v1_export_csv_quick_get",
        "security": [
          {
            "OAuth2PasswordBearer": []
          }
        ],
        "parameters": [
          {
            "name": "file_ids",
            "in": "query",
            "required": true,
            "schema": {
              "type": "string",
              "description": "Comma-separated file IDs",
              "title": "File Ids"
            },
            "description": "Comma-separated file IDs"
          },
          {
            "name": "start_date",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string",
                  "format": "date"
                },
                {
                  "type": "null"
                }
              ],
              "description": "Start date filter",
              "title": "Start Date"
            },
            "description": "Start date filter"
          },
          {
            "name": "end_date",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string",
                  "format": "date"
                },
                {
                  "type": "null"
                }
              ],
              "description": "End date filter",
              "title": "End Date"
            },
            "description": "End date filter"
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "ActivityDataColumnar": {
        "properties": {
          "timestamps": {
            "items": {
              "type": "number"
            },
            "type": "array",
            "title": "Timestamps",
            "description": "Unix timestamps"
          },
          "axis_x": {
            "items": {
              "type": "integer"
            },
            "type": "array",
            "title": "Axis X"
          },
          "axis_y": {
            "items": {
              "type": "integer"
            },
            "type": "array",
            "title": "Axis Y"
          },
          "axis_z": {
            "items": {
              "type": "integer"
            },
            "type": "array",
            "title": "Axis Z"
          },
          "vector_magnitude": {
            "items": {
              "type": "integer"
            },
            "type": "array",
            "title": "Vector Magnitude"
          }
        },
        "type": "object",
        "title": "ActivityDataColumnar",
        "description": "Columnar format for efficient JSON transfer.\n\nThis format reduces JSON overhead by using arrays instead of\nrepeated object keys for each data point."
      },
      "ActivityDataResponse": {
        "properties": {
          "data": {
            "$ref": "#/components/schemas/ActivityDataColumnar"
          },
          "available_dates": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Available Dates"
          },
          "current_date_index": {
            "type": "integer",
            "title": "Current Date Index",
            "default": 0
          },
          "algorithm_results": {
            "anyOf": [
              {
                "items": {
                  "type": "integer"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "title": "Algorithm Results"
          },
          "nonwear_results": {
            "anyOf": [
              {
                "items": {
                  "type": "integer"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "title": "Nonwear Results"
          },
          "file_id": {
            "type": "integer",
            "title": "File Id"
          },
          "analysis_date": {
            "type": "string",
            "title": "Analysis Date"
          },
          "view_start": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "View Start"
          },
          "view_end": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "View End"
          }
        },
        "type": "object",
        "required": [
          "data",
          "file_id",
          "analysis_date"
        ],
        "title": "ActivityDataResponse",
        "description": "Response for activity data endpoint."
      },
      "AlgorithmType": {
        "type": "string",
        "enum": [
          "sadeh_1994_original",
          "sadeh_1994_actilife",
          "cole_kripke_1992_original",
          "cole_kripke_1992_actilife",
          "manual"
        ],
        "title": "AlgorithmType",
        "description": "Sleep scoring algorithm identifiers.\n\nThese values match the algorithm IDs registered in AlgorithmFactory."
      },
      "Body_login_api_v1_auth_login_post": {
        "properties": {
          "grant_type": {
            "anyOf": [
              {
                "type": "string",
                "pattern": "^password$"
              },
              {
                "type": "null"
              }
            ],
            "title": "Grant Type"
          },
          "username": {
            "type": "string",
            "title": "Username"
          },
          "password": {
            "type": "string",
            "format": "password",
            "title": "Password"
          },
          "scope": {
            "type": "string",
            "title": "Scope",
            "default": ""
          },
          "client_id": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Client Id"
          },
          "client_secret": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "format": "password",
            "title": "Client Secret"
          }
        },
        "type": "object",
        "required": [
          "username",
          "password"
        ],
        "title": "Body_login_api_v1_auth_login_post"
      },
      "Body_upload_file_api_v1_files_upload_post": {
        "properties": {
          "file": {
            "type": "string",
            "format": "binary",
            "title": "File",
            "description": "CSV file to upload"
          }
        },
        "type": "object",
        "required": [
          "file"
        ],
        "title": "Body_upload_file_api_v1_files_upload_post"
      },
      "ExportColumnCategory": {
        "properties": {
          "name": {
            "type": "string",
            "title": "Name",
            "description": "Category display name"
          },
          "columns": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Columns",
            "description": "Column names in this category"
          }
        },
        "type": "object",
        "required": [
          "name"
        ],
        "title": "ExportColumnCategory",
        "description": "Category of export columns (e.g., Participant Info, Sleep Metrics)."
      },
      "ExportColumnInfo": {
        "properties": {
          "name": {
            "type": "string",
            "title": "Name",
            "description": "Column name as it appears in CSV"
          },
          "category": {
            "type": "string",
            "title": "Category",
            "description": "Category for grouping in UI"
          },
          "description": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Description",
            "description": "Human-readable description"
          },
          "data_type": {
            "type": "string",
            "title": "Data Type",
            "description": "Data type: string, number, datetime",
            "default": "string"
          },
          "is_default": {
            "type": "boolean",
            "title": "Is Default",
            "description": "Whether included in default export",
            "default": true
          }
        },
        "type": "object",
        "required": [
          "name",
          "category"
        ],
        "title": "ExportColumnInfo",
        "description": "Information about an available export column."
      },
      "ExportColumnsResponse": {
        "properties": {
          "columns": {
            "items": {
              "$ref": "#/components/schemas/ExportColumnInfo"
            },
            "type": "array",
            "title": "Columns"
          },
          "categories": {
            "items": {
              "$ref": "#/components/schemas/ExportColumnCategory"
            },
            "type": "array",
            "title": "Categories"
          }
        },
        "type": "object",
        "title": "ExportColumnsResponse",
        "description": "Response listing all available export columns."
      },
      "ExportRequest": {
        "properties": {
          "file_ids": {
            "items": {
              "type": "integer"
            },
            "type": "array",
            "title": "File Ids",
            "description": "File IDs to include in export"
          },
          "date_range": {
            "anyOf": [
              {
                "prefixItems": [
                  {
                    "type": "string",
                    "format": "date"
                  },
                  {
                    "type": "string",
                    "format": "date"
                  }
                ],
                "type": "array",
                "maxItems": 2,
                "minItems": 2
              },
              {
                "type": "null"
              }
            ],
            "title": "Date Range",
            "description": "Optional date range filter"
          },
          "columns": {
            "anyOf": [
              {
                "items": {
                  "type": "string"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "title": "Columns",
            "description": "Columns to include (None = all)"
          },
          "include_header": {
            "type": "boolean",
            "title": "Include Header",
            "description": "Include CSV header row",
            "default": true
          },
          "include_metadata": {
            "type": "boolean",
            "title": "Include Metadata",
            "description": "Include metadata comments at top",
            "default": false
          },
          "export_nonwear_separate": {
            "type": "boolean",
            "title": "Export Nonwear Separate",
            "description": "Export nonwear markers to separate file",
            "default": false
          }
        },
        "type": "object",
        "required": [
          "file_ids"
        ],
        "title": "ExportRequest",
        "description": "Request to generate a CSV export."
      },
      "ExportResponse": {
        "properties": {
          "success": {
            "type": "boolean",
            "title": "Success"
          },
          "filename": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Filename"
          },
          "row_count": {
            "type": "integer",
            "title": "Row Count",
            "default": 0
          },
          "file_count": {
            "type": "integer",
            "title": "File Count",
            "default": 0
          },
          "message": {
            "type": "string",
            "title": "Message",
            "default": ""
          },
          "warnings": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Warnings"
          }
        },
        "type": "object",
        "required": [
          "success"
        ],
        "title": "ExportResponse",
        "description": "Response after generating an export."
      },
      "FileInfo": {
        "properties": {
          "id": {
            "type": "integer",
            "title": "Id"
          },
          "filename": {
            "type": "string",
            "title": "Filename"
          },
          "original_path": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Original Path"
          },
          "file_type": {
            "type": "string",
            "title": "File Type",
            "default": "csv"
          },
          "status": {
            "$ref": "#/components/schemas/FileStatus",
            "default": "pending"
          },
          "row_count": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Row Count"
          },
          "start_time": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "Start Time"
          },
          "end_time": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "End Time"
          },
          "uploaded_by_id": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Uploaded By Id"
          },
          "uploaded_at": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "Uploaded At"
          }
        },
        "type": "object",
        "required": [
          "id",
          "filename"
        ],
        "title": "FileInfo",
        "description": "File metadata for listing."
      },
      "FileListResponse": {
        "properties": {
          "files": {
            "items": {
              "$ref": "#/components/schemas/FileInfo"
            },
            "type": "array",
            "title": "Files"
          },
          "total": {
            "type": "integer",
            "title": "Total"
          }
        },
        "type": "object",
        "required": [
          "files",
          "total"
        ],
        "title": "FileListResponse",
        "description": "Response for file listing endpoint."
      },
      "FileStatus": {
        "type": "string",
        "enum": [
          "pending",
          "processing",
          "ready",
          "failed"
        ],
        "title": "FileStatus",
        "description": "File processing status."
      },
      "FileUploadResponse": {
        "properties": {
          "file_id": {
            "type": "integer",
            "title": "File Id"
          },
          "filename": {
            "type": "string",
            "title": "Filename"
          },
          "status": {
            "$ref": "#/components/schemas/FileStatus"
          },
          "row_count": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Row Count"
          },
          "message": {
            "type": "string",
            "title": "Message",
            "default": "File uploaded successfully"
          }
        },
        "type": "object",
        "required": [
          "file_id",
          "filename",
          "status"
        ],
        "title": "FileUploadResponse",
        "description": "Response after file upload."
      },
      "HTTPValidationError": {
        "properties": {
          "detail": {
            "items": {
              "$ref": "#/components/schemas/ValidationError"
            },
            "type": "array",
            "title": "Detail"
          }
        },
        "type": "object",
        "title": "HTTPValidationError"
      },
      "ManualNonwearPeriod": {
        "properties": {
          "start_timestamp": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Start Timestamp"
          },
          "end_timestamp": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "End Timestamp"
          },
          "marker_index": {
            "type": "integer",
            "title": "Marker Index",
            "default": 1
          },
          "source": {
            "$ref": "#/components/schemas/NonwearDataSource",
            "default": "manual"
          }
        },
        "type": "object",
        "title": "ManualNonwearPeriod",
        "description": "Individual manual nonwear period with timestamps.\n\nPorted from desktop's dataclasses_markers.ManualNonwearPeriod."
      },
      "MarkerCategory": {
        "type": "string",
        "enum": [
          "sleep",
          "nonwear"
        ],
        "title": "MarkerCategory",
        "description": "Category of marker for styling and routing."
      },
      "MarkerType": {
        "type": "string",
        "enum": [
          "MAIN_SLEEP",
          "NAP"
        ],
        "title": "MarkerType",
        "description": "Sleep marker type classifications."
      },
      "MarkerUpdateRequest": {
        "properties": {
          "sleep_markers": {
            "anyOf": [
              {
                "items": {
                  "$ref": "#/components/schemas/SleepPeriod"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "title": "Sleep Markers"
          },
          "nonwear_markers": {
            "anyOf": [
              {
                "items": {
                  "$ref": "#/components/schemas/ManualNonwearPeriod"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "title": "Nonwear Markers"
          },
          "algorithm_used": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/AlgorithmType"
              },
              {
                "type": "null"
              }
            ]
          },
          "notes": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Notes"
          }
        },
        "type": "object",
        "title": "MarkerUpdateRequest",
        "description": "Request to update markers for a file/date."
      },
      "MarkersWithMetricsResponse": {
        "properties": {
          "sleep_markers": {
            "items": {
              "$ref": "#/components/schemas/SleepPeriod"
            },
            "type": "array",
            "title": "Sleep Markers"
          },
          "nonwear_markers": {
            "items": {
              "$ref": "#/components/schemas/ManualNonwearPeriod"
            },
            "type": "array",
            "title": "Nonwear Markers"
          },
          "metrics": {
            "items": {
              "$ref": "#/components/schemas/SleepMetrics"
            },
            "type": "array",
            "title": "Metrics"
          },
          "algorithm_results": {
            "anyOf": [
              {
                "items": {
                  "type": "integer"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "title": "Algorithm Results"
          },
          "verification_status": {
            "$ref": "#/components/schemas/VerificationStatus",
            "default": "draft"
          },
          "last_modified_at": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "Last Modified At"
          },
          "is_dirty": {
            "type": "boolean",
            "title": "Is Dirty",
            "default": false
          }
        },
        "type": "object",
        "title": "MarkersWithMetricsResponse",
        "description": "Response with markers and their calculated metrics."
      },
      "NonwearDataSource": {
        "type": "string",
        "enum": [
          "choi_algorithm",
          "manual"
        ],
        "title": "NonwearDataSource",
        "description": "Nonwear data source types."
      },
      "OnsetOffsetDataPoint": {
        "properties": {
          "timestamp": {
            "type": "number",
            "title": "Timestamp"
          },
          "datetime_str": {
            "type": "string",
            "title": "Datetime Str"
          },
          "axis_y": {
            "type": "integer",
            "title": "Axis Y"
          },
          "vector_magnitude": {
            "type": "integer",
            "title": "Vector Magnitude"
          },
          "algorithm_result": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Algorithm Result"
          }
        },
        "type": "object",
        "required": [
          "timestamp",
          "datetime_str",
          "axis_y",
          "vector_magnitude"
        ],
        "title": "OnsetOffsetDataPoint",
        "description": "Single data point for onset/offset tables."
      },
      "OnsetOffsetTableResponse": {
        "properties": {
          "onset_data": {
            "items": {
              "$ref": "#/components/schemas/OnsetOffsetDataPoint"
            },
            "type": "array",
            "title": "Onset Data"
          },
          "offset_data": {
            "items": {
              "$ref": "#/components/schemas/OnsetOffsetDataPoint"
            },
            "type": "array",
            "title": "Offset Data"
          },
          "period_index": {
            "type": "integer",
            "title": "Period Index"
          }
        },
        "type": "object",
        "required": [
          "period_index"
        ],
        "title": "OnsetOffsetTableResponse",
        "description": "Response with data points around a marker for tables."
      },
      "SaveStatusResponse": {
        "properties": {
          "success": {
            "type": "boolean",
            "title": "Success"
          },
          "saved_at": {
            "type": "string",
            "format": "date-time",
            "title": "Saved At"
          },
          "sleep_marker_count": {
            "type": "integer",
            "title": "Sleep Marker Count"
          },
          "nonwear_marker_count": {
            "type": "integer",
            "title": "Nonwear Marker Count"
          },
          "message": {
            "type": "string",
            "title": "Message",
            "default": "Markers saved successfully"
          }
        },
        "type": "object",
        "required": [
          "success",
          "saved_at",
          "sleep_marker_count",
          "nonwear_marker_count"
        ],
        "title": "SaveStatusResponse",
        "description": "Response after saving markers."
      },
      "SleepMetrics": {
        "properties": {
          "in_bed_time": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "In Bed Time"
          },
          "out_bed_time": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "Out Bed Time"
          },
          "sleep_onset": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "Sleep Onset"
          },
          "sleep_offset": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "Sleep Offset"
          },
          "time_in_bed_minutes": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Time In Bed Minutes"
          },
          "total_sleep_time_minutes": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Total Sleep Time Minutes"
          },
          "sleep_onset_latency_minutes": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Sleep Onset Latency Minutes"
          },
          "waso_minutes": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Waso Minutes"
          },
          "number_of_awakenings": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Number Of Awakenings"
          },
          "average_awakening_length_minutes": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Average Awakening Length Minutes"
          },
          "sleep_efficiency": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Sleep Efficiency"
          },
          "movement_index": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Movement Index"
          },
          "fragmentation_index": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Fragmentation Index"
          },
          "sleep_fragmentation_index": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Sleep Fragmentation Index"
          },
          "total_activity": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Total Activity"
          },
          "nonzero_epochs": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "title": "Nonzero Epochs"
          }
        },
        "type": "object",
        "title": "SleepMetrics",
        "description": "Complete sleep quality metrics for a single sleep period.\n\nImplements Tudor-Locke metrics algorithm as defined in the\nactigraph.sleepr R package.\n\nReference:\n    Tudor-Locke C, et al. (2014). Fully automated waist-worn accelerometer algorithm\n    for detecting children's sleep-period time. Applied Physiology, Nutrition, and\n    Metabolism, 39(1):53-57."
      },
      "SleepPeriod": {
        "properties": {
          "onset_timestamp": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Onset Timestamp"
          },
          "offset_timestamp": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Offset Timestamp"
          },
          "marker_index": {
            "type": "integer",
            "title": "Marker Index",
            "default": 1
          },
          "marker_type": {
            "$ref": "#/components/schemas/MarkerType",
            "default": "MAIN_SLEEP"
          }
        },
        "type": "object",
        "title": "SleepPeriod",
        "description": "Individual sleep period with onset/offset timestamps.\n\nPorted from desktop's dataclasses_markers.SleepPeriod."
      },
      "Token": {
        "properties": {
          "access_token": {
            "type": "string",
            "title": "Access Token"
          },
          "refresh_token": {
            "type": "string",
            "title": "Refresh Token"
          },
          "token_type": {
            "type": "string",
            "title": "Token Type",
            "default": "bearer"
          }
        },
        "type": "object",
        "required": [
          "access_token",
          "refresh_token"
        ],
        "title": "Token",
        "description": "JWT token response."
      },
      "TokenRefresh": {
        "properties": {
          "refresh_token": {
            "type": "string",
            "title": "Refresh Token"
          }
        },
        "type": "object",
        "required": [
          "refresh_token"
        ],
        "title": "TokenRefresh",
        "description": "Token refresh request."
      },
      "UserCreate": {
        "properties": {
          "email": {
            "type": "string",
            "title": "Email"
          },
          "username": {
            "type": "string",
            "title": "Username"
          },
          "password": {
            "type": "string",
            "title": "Password"
          },
          "role": {
            "type": "string",
            "title": "Role",
            "default": "annotator"
          }
        },
        "type": "object",
        "required": [
          "email",
          "username",
          "password"
        ],
        "title": "UserCreate",
        "description": "User creation request."
      },
      "UserRead": {
        "properties": {
          "id": {
            "type": "integer",
            "title": "Id"
          },
          "email": {
            "type": "string",
            "title": "Email"
          },
          "username": {
            "type": "string",
            "title": "Username"
          },
          "role": {
            "type": "string",
            "title": "Role",
            "default": "annotator"
          },
          "is_active": {
            "type": "boolean",
            "title": "Is Active",
            "default": true
          },
          "created_at": {
            "anyOf": [
              {
                "type": "string",
                "format": "date-time"
              },
              {
                "type": "null"
              }
            ],
            "title": "Created At"
          }
        },
        "type": "object",
        "required": [
          "id",
          "email",
          "username"
        ],
        "title": "UserRead",
        "description": "User response model."
      },
      "ValidationError": {
        "properties": {
          "loc": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array",
            "title": "Location"
          },
          "msg": {
            "type": "string",
            "title": "Message"
          },
          "type": {
            "type": "string",
            "title": "Error Type"
          }
        },
        "type": "object",
        "required": [
          "loc",
          "msg",
          "type"
        ],
        "title": "ValidationError"
      },
      "VerificationStatus": {
        "type": "string",
        "enum": [
          "draft",
          "submitted",
          "verified",
          "disputed",
          "resolved"
        ],
        "title": "VerificationStatus",
        "description": "Verification status for annotations."
      }
    },
    "securitySchemes": {
      "OAuth2PasswordBearer": {
        "type": "oauth2",
        "flows": {
          "password": {
            "scopes": {},
            "tokenUrl": "/api/v1/auth/login"
          }
        }
      }
    }
  }
} as const;
