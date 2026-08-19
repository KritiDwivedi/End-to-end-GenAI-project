from __future__ import annotations

from functools import lru_cache

from supabase import Client, ClientOptions, create_client

from app.config import settings


def _client_options(*, headers: dict[str, str] | None = None) -> ClientOptions:
    return ClientOptions(
        schema="public",
        headers=headers or {},
        auto_refresh_token=False,
        persist_session=False,
        detect_session_in_url=False,
        flow_type="pkce",
    )


@lru_cache
def get_supabase_anon_client() -> Client:
    """Return a cached Supabase client authenticated with the anon key."""
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key_value,
        options=_client_options(),
    )


@lru_cache
def get_supabase_service_client() -> Client:
    """Return a cached Supabase client authenticated with the service role key."""
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key_value,
        options=_client_options(),
    )


def get_supabase_user_client(access_token: str) -> Client:
    """Return a request-scoped Supabase client for the current user token."""
    token = access_token.strip()
    if not token:
        raise ValueError("access_token must not be empty")

    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key_value,
        options=_client_options(
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_anon_key_value,
            }
        ),
    )


def get_supabase_client(*, access_token: str | None = None, use_service_role: bool = False) -> Client:
    """Return the appropriate Supabase client for the current use case."""
    if use_service_role:
        return get_supabase_service_client()
    if access_token:
        return get_supabase_user_client(access_token)
    return get_supabase_anon_client()


def reset_supabase_clients() -> None:
    """Clear cached client singletons, useful in tests."""
    get_supabase_anon_client.cache_clear()
    get_supabase_service_client.cache_clear()


__all__ = [
    "get_supabase_anon_client",
    "get_supabase_client",
    "get_supabase_service_client",
    "get_supabase_user_client",
    "reset_supabase_clients",
]
