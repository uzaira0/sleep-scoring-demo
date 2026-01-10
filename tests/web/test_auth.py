"""
Tests for authentication API endpoints.

Tests cover:
- User registration
- Login with username/email
- Token refresh
- Get current user
- Invalid credentials handling
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient) -> None:
        """Test successful user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.local",
                "username": "newuser",
                "password": "securepassword123",
                "role": "annotator",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.local"
        assert data["username"] == "newuser"
        assert data["role"] == "annotator"
        assert "id" in data
        assert "hashed_password" not in data  # Should not expose password

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        """Test registration fails with duplicate email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "admin@test.local",  # Same as pre-created admin
                "username": "differentuser",
                "password": "securepassword123",
            },
        )
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient) -> None:
        """Test registration fails with duplicate username."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "different@test.local",
                "username": "testadmin",  # Same as pre-created admin
                "password": "securepassword123",
            },
        )
        assert response.status_code == 400
        assert "Username already taken" in response.json()["detail"]


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    @pytest.mark.asyncio
    async def test_login_with_username(self, client: AsyncClient) -> None:
        """Test login with username."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testadmin", "password": "testpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_with_email(self, client: AsyncClient) -> None:
        """Test login with email."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@test.local", "password": "testpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient) -> None:
        """Test login fails with wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testadmin", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        """Test login fails for nonexistent user."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent", "password": "anypassword"},
        )
        assert response.status_code == 401


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient) -> None:
        """Test token refresh with valid refresh token."""
        # First, login to get tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testadmin", "password": "testpass123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh the token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(self, client: AsyncClient) -> None:
        """Test refresh fails with invalid token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_access_token(
        self, client: AsyncClient, admin_token: str
    ) -> None:
        """Test refresh fails when using access token instead of refresh token."""
        # Access tokens have type="access", refresh tokens have type="refresh"
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": admin_token},  # This is an access token
        )
        assert response.status_code == 401


class TestGetMe:
    """Tests for GET /api/v1/auth/me."""

    @pytest.mark.asyncio
    async def test_get_me_authenticated(
        self, client: AsyncClient, admin_auth_headers: dict[str, str]
    ) -> None:
        """Test get current user when authenticated."""
        response = await client.get("/api/v1/auth/me", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"
        assert data["email"] == "admin@test.local"
        assert data["role"] == "admin"

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client: AsyncClient) -> None:
        """Test get current user fails without authentication."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client: AsyncClient) -> None:
        """Test get current user fails with invalid token."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401


class TestAuthRoles:
    """Tests for role-based authentication."""

    @pytest.mark.asyncio
    async def test_admin_user_role(
        self, client: AsyncClient, admin_auth_headers: dict[str, str]
    ) -> None:
        """Test admin user has admin role."""
        response = await client.get("/api/v1/auth/me", headers=admin_auth_headers)
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    @pytest.mark.asyncio
    async def test_annotator_user_role(
        self, client: AsyncClient, annotator_auth_headers: dict[str, str]
    ) -> None:
        """Test annotator user has annotator role."""
        response = await client.get("/api/v1/auth/me", headers=annotator_auth_headers)
        assert response.status_code == 200
        assert response.json()["role"] == "annotator"
