from __future__ import annotations

from collections import Counter
import os
import time
from typing import Any

import requests
import streamlit as st


PUBLIC_SUPABASE_CONFIG = {
    "SUPABASE_URL": "https://mortkrburieahfxjykte.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_410RxXgZogBcWwMHpkXtCQ_tUqGPVyr",
}
REQUEST_TIMEOUT = 15
PUBLIC_APP_URL = "https://ai-hunt-china.streamlit.app/"


def _secret(name: str) -> str:
    try:
        value = str(st.secrets.get(name, "")).strip()
    except Exception:
        value = ""
    return value or os.getenv(name, "").strip() or PUBLIC_SUPABASE_CONFIG.get(name, "")


def _api_key() -> str:
    return _secret("SUPABASE_PUBLISHABLE_KEY") or _secret("SUPABASE_ANON_KEY")


def configured() -> bool:
    return bool(_secret("SUPABASE_URL") and _api_key())


def _headers(authenticated: bool = False) -> dict[str, str]:
    headers = {"apikey": _api_key(), "Content-Type": "application/json"}
    if authenticated and st.session_state.get("access_token"):
        headers["Authorization"] = f"Bearer {st.session_state['access_token']}"
    return headers


def _request(method: str, path: str, *, authenticated: bool = False, **kwargs: Any) -> requests.Response:
    headers = _headers(authenticated)
    headers.update(kwargs.pop("headers", {}))
    response = requests.request(
        method,
        f"{_secret('SUPABASE_URL')}{path}",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise RuntimeError(detail)
    return response


def _store_session(payload: dict[str, Any]) -> None:
    if not payload.get("access_token"):
        return
    user = payload.get("user") or {}
    st.session_state["access_token"] = payload["access_token"]
    st.session_state["refresh_token"] = payload.get("refresh_token", "")
    st.session_state["expires_at"] = int(payload.get("expires_at") or time.time() + payload.get("expires_in", 3600))
    st.session_state["user_id"] = user.get("id", "")
    st.session_state["user_email"] = user.get("email", "")


def clear_session() -> None:
    for key in ("access_token", "refresh_token", "expires_at", "user_id", "user_email"):
        st.session_state.pop(key, None)


def _refresh_session_if_needed() -> None:
    if not is_logged_in() or time.time() < st.session_state.get("expires_at", 0) - 60:
        return
    refresh_token = st.session_state.get("refresh_token")
    if not refresh_token:
        clear_session()
        return
    try:
        response = _request(
            "POST",
            "/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": refresh_token},
        )
        _store_session(response.json())
    except Exception:
        clear_session()


def sign_in(email: str, password: str) -> tuple[bool, str]:
    if not configured():
        return False, "账号服务尚未配置"
    try:
        response = _request(
            "POST",
            "/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
        )
        _store_session(response.json())
        return True, "登录成功"
    except Exception as exc:
        return False, friendly_error(exc)


def sign_up(email: str, password: str) -> tuple[bool, str]:
    if not configured():
        return False, "账号服务尚未配置"
    try:
        response = _request(
            "POST",
            "/auth/v1/signup",
            params={"redirect_to": PUBLIC_APP_URL},
            json={"email": email, "password": password},
        )
        payload = response.json()
        if payload.get("access_token"):
            _store_session(payload)
            return True, "注册成功"
        return True, "注册成功，请到邮箱完成验证后登录"
    except Exception as exc:
        return False, friendly_error(exc)


def resend_signup(email: str) -> tuple[bool, str]:
    if not configured():
        return False, "账号服务尚未配置"
    if not email:
        return False, "请先填写注册邮箱"
    try:
        _request(
            "POST",
            "/auth/v1/resend",
            params={"redirect_to": PUBLIC_APP_URL},
            json={"type": "signup", "email": email},
        )
        return True, "验证邮件已重新发送，请检查收件箱和垃圾邮件"
    except Exception as exc:
        return False, friendly_error(exc)


def sign_out() -> None:
    if is_logged_in():
        try:
            _request("POST", "/auth/v1/logout", authenticated=True)
        except Exception:
            pass
    clear_session()


def is_logged_in() -> bool:
    return bool(st.session_state.get("user_id") and st.session_state.get("access_token"))


def favorite_state(product_keys: list[str]) -> tuple[set[str], Counter[str]]:
    if not configured() or not product_keys:
        return set(), Counter()
    counts: Counter[str] = Counter()
    mine: set[str] = set()
    try:
        response = _request(
            "POST",
            "/rest/v1/rpc/get_favorite_counts",
            json={"product_keys": product_keys},
        )
        counts.update({row["product_key"]: int(row["favorite_count"]) for row in response.json()})
        if is_logged_in():
            _refresh_session_if_needed()
            response = _request(
                "GET",
                "/rest/v1/favorites",
                authenticated=True,
                params={"select": "product_key", "product_key": f"in.({','.join(product_keys)})"},
            )
            mine = {row["product_key"] for row in response.json()}
    except Exception:
        return mine, counts
    return mine, counts


def set_favorite(product_key: str, product_date: str, active: bool) -> tuple[bool, str]:
    if not is_logged_in():
        return False, "请先登录后收藏"
    if not configured():
        return False, "收藏服务尚未配置"
    _refresh_session_if_needed()
    if not is_logged_in():
        return False, "登录已过期，请重新登录"
    try:
        if active:
            _request(
                "POST",
                "/rest/v1/favorites?on_conflict=user_id,product_key",
                authenticated=True,
                headers={**_headers(True), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json={
                    "user_id": st.session_state["user_id"],
                    "product_key": product_key,
                    "product_date": product_date,
                },
            )
        else:
            _request(
                "DELETE",
                "/rest/v1/favorites",
                authenticated=True,
                params={"product_key": f"eq.{product_key}"},
            )
        return True, "已收藏" if active else "已取消收藏"
    except Exception as exc:
        return False, friendly_error(exc)


def friendly_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "invalid login" in message or "invalid credentials" in message:
        return "邮箱或密码不正确"
    if "already registered" in message or "already been registered" in message or "user already registered" in message:
        return "该邮箱已经注册"
    if "password" in message and ("characters" in message or "weak" in message):
        return "密码至少需要 6 位"
    if "email" in message and "confirm" in message:
        return "请先完成邮箱验证"
    if "email address not authorized" in message or "not authorized" in message:
        return "当前邮件服务不允许向该邮箱发送，请联系管理员配置正式邮件服务"
    if "rate limit" in message or "over_email_send_rate_limit" in message:
        return "验证邮件发送过于频繁，请稍后再试"
    return "操作失败，请稍后重试"
