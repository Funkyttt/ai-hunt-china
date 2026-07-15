from __future__ import annotations

from collections import Counter
from typing import Any

import streamlit as st

try:
    from supabase import Client, create_client
except ImportError:  # The public catalog still works before dependencies finish installing.
    Client = Any
    create_client = None


def _secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def configured() -> bool:
    return bool(_secret("SUPABASE_URL") and _secret("SUPABASE_ANON_KEY") and create_client)


def client() -> Client | None:
    if not configured():
        return None
    db = create_client(_secret("SUPABASE_URL"), _secret("SUPABASE_ANON_KEY"))
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    if access_token and refresh_token:
        try:
            response = db.auth.set_session(access_token, refresh_token)
            _store_session(response.session)
        except Exception:
            clear_session()
    return db


def _store_session(session: Any) -> None:
    if not session:
        return
    st.session_state["access_token"] = session.access_token
    st.session_state["refresh_token"] = session.refresh_token
    st.session_state["user_id"] = session.user.id
    st.session_state["user_email"] = session.user.email


def clear_session() -> None:
    for key in ("access_token", "refresh_token", "user_id", "user_email"):
        st.session_state.pop(key, None)


def sign_in(email: str, password: str) -> tuple[bool, str]:
    db = client()
    if not db:
        return False, "账号服务尚未配置"
    try:
        response = db.auth.sign_in_with_password({"email": email, "password": password})
        _store_session(response.session)
        return True, "登录成功"
    except Exception as exc:
        return False, friendly_error(exc)


def sign_up(email: str, password: str) -> tuple[bool, str]:
    db = client()
    if not db:
        return False, "账号服务尚未配置"
    try:
        response = db.auth.sign_up({"email": email, "password": password})
        if response.session:
            _store_session(response.session)
            return True, "注册成功"
        return True, "注册成功，请到邮箱完成验证后登录"
    except Exception as exc:
        return False, friendly_error(exc)


def sign_out() -> None:
    db = client()
    if db:
        try:
            db.auth.sign_out()
        except Exception:
            pass
    clear_session()


def is_logged_in() -> bool:
    return bool(st.session_state.get("user_id"))


def favorite_state(product_keys: list[str]) -> tuple[set[str], Counter[str]]:
    db = client()
    if not db or not product_keys:
        return set(), Counter()
    counts: Counter[str] = Counter()
    mine: set[str] = set()
    try:
        count_rows = db.table("favorite_counts").select("product_key,favorite_count").in_("product_key", product_keys).execute().data
        counts.update({row["product_key"]: int(row["favorite_count"]) for row in count_rows})
        if is_logged_in():
            rows = db.table("favorites").select("product_key").in_("product_key", product_keys).execute().data
            mine = {row["product_key"] for row in rows}
    except Exception:
        return mine, counts
    return mine, counts


def set_favorite(product_key: str, product_date: str, active: bool) -> tuple[bool, str]:
    if not is_logged_in():
        return False, "请先登录后收藏"
    db = client()
    if not db:
        return False, "收藏服务尚未配置"
    try:
        if active:
            db.table("favorites").upsert(
                {
                    "user_id": st.session_state["user_id"],
                    "product_key": product_key,
                    "product_date": product_date,
                }
            ).execute()
        else:
            db.table("favorites").delete().eq("product_key", product_key).execute()
        return True, "已收藏" if active else "已取消收藏"
    except Exception as exc:
        return False, friendly_error(exc)


def friendly_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "invalid login" in message or "invalid credentials" in message:
        return "邮箱或密码不正确"
    if "already registered" in message or "already been registered" in message:
        return "该邮箱已经注册"
    if "password" in message and "characters" in message:
        return "密码至少需要 6 位"
    if "email" in message and "confirm" in message:
        return "请先完成邮箱验证"
    return "操作失败，请稍后重试"
