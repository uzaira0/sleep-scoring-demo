"""
Tests for file management API endpoints.

Tests cover:
- File upload
- File listing
- File retrieval by ID
- File deletion (admin only)
- File dates retrieval
- Data directory scanning (admin only)
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from httpx import AsyncClient


class TestFileUpload:
    """Tests for POST /api/v1/files/upload."""

    @pytest.mark.asyncio
    async def test_upload_csv_success(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        sample_csv_content: str,
    ) -> None:
        """Test successful CSV file upload."""
        files = {
            "file": ("test_data.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
        }
        response = await client.post(
            "/api/v1/files/upload",
            files=files,
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test_data.csv"
        assert data["status"] == "ready"
        assert data["row_count"] == 100  # 100 rows in sample data
        assert "file_id" in data

    @pytest.mark.asyncio
    async def test_upload_without_auth(
        self, client: AsyncClient, sample_csv_content: str
    ) -> None:
        """Test upload fails without authentication."""
        files = {
            "file": ("test_data.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
        }
        response = await client.post("/api/v1/files/upload", files=files)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_duplicate_file(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        sample_csv_content: str,
    ) -> None:
        """Test upload fails for duplicate filename."""
        files = {
            "file": ("duplicate.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
        }
        # First upload
        response1 = await client.post(
            "/api/v1/files/upload",
            files=files,
            headers=admin_auth_headers,
        )
        assert response1.status_code == 200

        # Second upload with same name
        files2 = {
            "file": ("duplicate.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
        }
        response2 = await client.post(
            "/api/v1/files/upload",
            files=files2,
            headers=admin_auth_headers,
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_invalid_extension(
        self, client: AsyncClient, admin_auth_headers: dict[str, str]
    ) -> None:
        """Test upload fails for unsupported file type."""
        files = {
            "file": ("test.txt", io.BytesIO(b"not a csv"), "text/plain")
        }
        response = await client.post(
            "/api/v1/files/upload",
            files=files,
            headers=admin_auth_headers,
        )
        assert response.status_code == 400
        assert "CSV and Excel files" in response.json()["detail"]


class TestFileList:
    """Tests for GET /api/v1/files."""

    @pytest.mark.asyncio
    async def test_list_files_empty(
        self, client: AsyncClient, admin_auth_headers: dict[str, str]
    ) -> None:
        """Test listing files when none exist."""
        response = await client.get("/api/v1/files", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_files_with_data(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        sample_csv_content: str,
    ) -> None:
        """Test listing files after upload."""
        # Upload a file first
        files = {
            "file": ("list_test.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
        }
        await client.post(
            "/api/v1/files/upload",
            files=files,
            headers=admin_auth_headers,
        )

        # List files
        response = await client.get("/api/v1/files", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(f["filename"] == "list_test.csv" for f in data["files"])

    @pytest.mark.asyncio
    async def test_list_files_pagination(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        sample_csv_content: str,
    ) -> None:
        """Test file listing with pagination."""
        # Upload multiple files
        for i in range(5):
            files = {
                "file": (f"page_test_{i}.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
            }
            await client.post(
                "/api/v1/files/upload",
                files=files,
                headers=admin_auth_headers,
            )

        # Test with limit
        response = await client.get(
            "/api/v1/files",
            params={"limit": 2},
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) <= 2
        assert data["total"] >= 5

    @pytest.mark.asyncio
    async def test_list_files_without_auth(self, client: AsyncClient) -> None:
        """Test listing files fails without authentication."""
        response = await client.get("/api/v1/files")
        assert response.status_code == 401


class TestFileGet:
    """Tests for GET /api/v1/files/{file_id}."""

    @pytest.mark.asyncio
    async def test_get_file_success(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        sample_csv_content: str,
    ) -> None:
        """Test getting file by ID."""
        # Upload a file first
        files = {
            "file": ("get_test.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
        }
        upload_response = await client.post(
            "/api/v1/files/upload",
            files=files,
            headers=admin_auth_headers,
        )
        file_id = upload_response.json()["file_id"]

        # Get file by ID
        response = await client.get(
            f"/api/v1/files/{file_id}",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "get_test.csv"
        assert data["id"] == file_id

    @pytest.mark.asyncio
    async def test_get_file_not_found(
        self, client: AsyncClient, admin_auth_headers: dict[str, str]
    ) -> None:
        """Test getting nonexistent file returns 404."""
        response = await client.get(
            "/api/v1/files/99999",
            headers=admin_auth_headers,
        )
        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]


class TestFileDelete:
    """Tests for DELETE /api/v1/files/{file_id}."""

    @pytest.mark.asyncio
    async def test_delete_file_as_admin(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        sample_csv_content: str,
    ) -> None:
        """Test admin can delete files."""
        # Upload a file first
        files = {
            "file": ("delete_test.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
        }
        upload_response = await client.post(
            "/api/v1/files/upload",
            files=files,
            headers=admin_auth_headers,
        )
        file_id = upload_response.json()["file_id"]

        # Delete the file
        response = await client.delete(
            f"/api/v1/files/{file_id}",
            headers=admin_auth_headers,
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(
            f"/api/v1/files/{file_id}",
            headers=admin_auth_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_file_as_annotator_forbidden(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        annotator_auth_headers: dict[str, str],
        sample_csv_content: str,
    ) -> None:
        """Test annotator cannot delete files."""
        # Upload a file as admin
        files = {
            "file": ("nodelete_test.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
        }
        upload_response = await client.post(
            "/api/v1/files/upload",
            files=files,
            headers=admin_auth_headers,
        )
        file_id = upload_response.json()["file_id"]

        # Try to delete as annotator
        response = await client.delete(
            f"/api/v1/files/{file_id}",
            headers=annotator_auth_headers,
        )
        assert response.status_code == 403
        assert "Only admins" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(
        self, client: AsyncClient, admin_auth_headers: dict[str, str]
    ) -> None:
        """Test deleting nonexistent file returns 404."""
        response = await client.delete(
            "/api/v1/files/99999",
            headers=admin_auth_headers,
        )
        assert response.status_code == 404


class TestFileDates:
    """Tests for GET /api/v1/files/{file_id}/dates."""

    @pytest.mark.asyncio
    async def test_get_file_dates(
        self,
        client: AsyncClient,
        admin_auth_headers: dict[str, str],
        sample_csv_content: str,
    ) -> None:
        """Test getting available dates for a file."""
        # Upload a file first
        files = {
            "file": ("dates_test.csv", io.BytesIO(sample_csv_content.encode()), "text/csv")
        }
        upload_response = await client.post(
            "/api/v1/files/upload",
            files=files,
            headers=admin_auth_headers,
        )
        file_id = upload_response.json()["file_id"]

        # Get dates
        response = await client.get(
            f"/api/v1/files/{file_id}/dates",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Our sample data is for 2024-01-01
        assert any("2024-01-01" in d for d in data)

    @pytest.mark.asyncio
    async def test_get_dates_file_not_found(
        self, client: AsyncClient, admin_auth_headers: dict[str, str]
    ) -> None:
        """Test getting dates for nonexistent file returns 404."""
        response = await client.get(
            "/api/v1/files/99999/dates",
            headers=admin_auth_headers,
        )
        assert response.status_code == 404


class TestFileScan:
    """Tests for POST /api/v1/files/scan and GET /api/v1/files/scan/status."""

    @pytest.mark.asyncio
    async def test_scan_as_admin(
        self, client: AsyncClient, admin_auth_headers: dict[str, str]
    ) -> None:
        """Test admin can trigger directory scan."""
        response = await client.post(
            "/api/v1/files/scan",
            headers=admin_auth_headers,
        )
        # May return 200 with started=False if no files exist
        # or 200 with started=True if files exist
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "total_files" in data

    @pytest.mark.asyncio
    async def test_scan_as_annotator_forbidden(
        self, client: AsyncClient, annotator_auth_headers: dict[str, str]
    ) -> None:
        """Test annotator cannot trigger directory scan."""
        response = await client.post(
            "/api/v1/files/scan",
            headers=annotator_auth_headers,
        )
        assert response.status_code == 403
        assert "Only admins" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_scan_status(
        self, client: AsyncClient, admin_auth_headers: dict[str, str]
    ) -> None:
        """Test getting scan status."""
        response = await client.get(
            "/api/v1/files/scan/status",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "total_files" in data
        assert "processed" in data
        assert "progress_percent" in data

    @pytest.mark.asyncio
    async def test_get_scan_status_without_auth(self, client: AsyncClient) -> None:
        """Test getting scan status fails without authentication."""
        response = await client.get("/api/v1/files/scan/status")
        assert response.status_code == 401
