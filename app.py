from __future__ import annotations

import base64
import json
import mimetypes
import os
from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st

import auth


ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "products.json"
HISTORY_DIR = ROOT / "data" / "history"

st.set_page_config(
    page_title="AI Hunt China",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="auto",
)


def safe(value: object) -> str:
    return escape(str(value or ""), quote=True)


@st.cache_data(ttl=60)
def load_history() -> dict[str, dict]:
    history: dict[str, dict] = {}
    if HISTORY_DIR.exists():
        for path in HISTORY_DIR.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                history[payload["date"]] = payload
            except (OSError, json.JSONDecodeError, KeyError):
                continue
    if DATA_FILE.exists():
        try:
            latest = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            history[latest["date"]] = latest
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    return history


@st.cache_data
def local_logo_data(path_value: str) -> str:
    path = ROOT / path_value
    if not path.exists() or not path.is_file():
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def logo_html(product: dict) -> str:
    source = local_logo_data(product.get("logo_path", "")) if product.get("logo_path") else ""
    if source:
        return f'<div class="logo"><img src="{safe(source)}" alt="{safe(product.get("name"))} logo"></div>'
    initials = "".join(part[0] for part in str(product.get("name", "AI")).split()[:2]).upper()[:2]
    return f'<div class="logo logo-fallback">{safe(initials or "AI")}</div>'


def date_label(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed.strftime("%Y 年 %m 月 %d 日")
    except ValueError:
        return value


def product_key(product: dict) -> str:
    return str(product.get("id") or product.get("slug") or product.get("name", "product"))


st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;600;700;900&display=swap');
:root { --cyan:#42e8ff; --pink:#ff4f91; --green:#66ffb5; --ink:#eef7ff; --muted:#8fa6bc; --panel:#0b1222; }
.stApp { background-color:#050713; background-image:linear-gradient(rgba(66,232,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(66,232,255,.025) 1px,transparent 1px);background-size:28px 28px;color:var(--ink); }
.stApp,button,input { font-family:Inter,"Noto Sans SC",sans-serif;letter-spacing:0; }
[data-testid="stHeader"] { background:rgba(3,5,13,.76);backdrop-filter:blur(16px); }
[data-testid="stSidebar"] { background:#070b17;border-right:1px solid rgba(66,232,255,.14); }
.block-container { max-width:1420px;padding-top:1.6rem; }
.brand { display:flex;align-items:center;gap:12px;font-size:14px;font-weight:800;color:#fff; }
.brand-mark { width:34px;height:34px;display:grid;place-items:center;background:#42e8ff;color:#041019;clip-path:polygon(18% 0,100% 0,82% 100%,0 100%); }
.eyebrow { color:var(--cyan);font-size:12px;font-weight:800; }
.hero { padding:16px 0 20px;border-bottom:1px solid rgba(143,166,188,.15);margin-bottom:18px; }
.hero h1 { margin:7px 0;font-size:clamp(32px,5vw,58px);line-height:1.03;font-weight:900; }
.hero h1 span { color:var(--cyan);text-shadow:0 0 24px rgba(66,232,255,.28); }
.hero p { color:var(--muted);margin:0;max-width:760px;font-size:14px; }
.pulse { display:inline-block;width:7px;height:7px;background:var(--green);border-radius:50%;box-shadow:0 0 12px var(--green);margin-right:7px; }
.product { display:grid;grid-template-columns:54px 58px minmax(0,1fr) 96px;gap:15px;align-items:center;min-height:106px;padding:16px 18px;background:rgba(11,18,34,.88);border:1px solid rgba(143,166,188,.16);border-left:2px solid transparent;transition:.18s ease;overflow:hidden; }
.product:hover { transform:translateY(-2px);border-color:rgba(66,232,255,.42);border-left-color:var(--cyan);background:#0e182b;box-shadow:0 14px 42px rgba(0,0,0,.3); }
.rank { font-size:24px;font-weight:900;color:rgba(238,247,255,.34);font-variant-numeric:tabular-nums; }
.rank.top { color:var(--cyan);text-shadow:0 0 16px rgba(66,232,255,.32); }
.logo { width:52px;height:52px;display:grid;place-items:center;background:#fff;border:1px solid rgba(255,255,255,.18);overflow:hidden; }
.logo img { width:100%;height:100%;object-fit:contain; }
.logo-fallback { background:#15233a;color:var(--cyan);font-size:15px;font-weight:900; }
.product h3 { margin:0 0 5px;font-size:18px; }
.product p { margin:0;color:var(--muted);font-size:13px;line-height:1.55; }
.chips { display:flex;gap:6px;flex-wrap:wrap;margin-top:8px; }
.chip { padding:3px 8px;border:1px solid rgba(66,232,255,.2);color:#aadfe8;background:rgba(66,232,255,.06);font-size:10px; }
.score { text-align:right;min-width:86px; }
.score strong { display:block;color:var(--green);font-size:20px; }
.score small { color:var(--muted);font-size:9px;text-transform:uppercase; }
.section-title { color:var(--cyan);font-size:12px;font-weight:800;margin:22px 0 7px;text-transform:uppercase; }
.detail-copy { color:#cbd8e5;line-height:1.8;font-size:14px; }
.metric { padding:12px;border:1px solid rgba(143,166,188,.15);background:rgba(11,18,34,.72); }
.metric b { display:block;color:#fff;font-size:18px; }.metric span { color:var(--muted);font-size:11px; }
.metrics { display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px; }
.user-box { padding:10px;border:1px solid rgba(102,255,181,.22);background:rgba(102,255,181,.05); }
.stButton>button,[data-testid="stButton"] button { border-radius:2px!important;border:1px solid rgba(66,232,255,.32)!important;background:#0b1b2a!important;color:#dffaff!important;min-height:38px; }
.stButton>button:hover,[data-testid="stButton"] button:hover { border-color:var(--cyan)!important;color:#fff!important;box-shadow:0 0 20px rgba(66,232,255,.13); }
@media(max-width:760px){.product{grid-template-columns:34px 46px minmax(0,1fr);padding:13px 10px;gap:9px}.logo{width:42px;height:42px}.score{display:none}.hero h1{font-size:36px}.block-container{padding:1rem}.product h3{font-size:16px}.product p{font-size:12px}.metrics{gap:5px}.metric{padding:9px 7px}.metric b{font-size:16px}}
</style>
""",
    unsafe_allow_html=True,
)


history = load_history()
available_dates = sorted(history.keys(), reverse=True)
if not available_dates:
    st.error("榜单数据尚未生成")
    st.stop()

with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">AI</div>HUNT CHINA</div>', unsafe_allow_html=True)
    st.caption("中国 AI 新品情报站")
    st.divider()

    if auth.configured():
        if auth.is_logged_in():
            st.markdown(f'<div class="user-box"><b>{safe(st.session_state.get("user_email"))}</b><br><small>账号已登录</small></div>', unsafe_allow_html=True)
            if st.button("退出登录", use_container_width=True):
                auth.sign_out()
                st.rerun()
        else:
            login_tab, register_tab = st.tabs(["登录", "注册"])
            with login_tab:
                with st.form("login-form"):
                    login_email = st.text_input("邮箱", key="login-email")
                    login_password = st.text_input("密码", type="password", key="login-password")
                    login_submit = st.form_submit_button("登录", use_container_width=True)
                if login_submit:
                    ok, message = auth.sign_in(login_email.strip(), login_password)
                    (st.success if ok else st.error)(message)
                    if ok:
                        st.rerun()
            with register_tab:
                with st.form("register-form"):
                    register_email = st.text_input("邮箱", key="register-email")
                    register_password = st.text_input("密码（至少 6 位）", type="password", key="register-password")
                    register_submit = st.form_submit_button("创建账号", use_container_width=True)
                if register_submit:
                    ok, message = auth.sign_up(register_email.strip(), register_password)
                    (st.success if ok else st.error)(message)
                    if ok and auth.is_logged_in():
                        st.rerun()
    else:
        st.caption("账号与收藏服务等待数据库配置")

    st.divider()
    selected_date = st.selectbox("榜单日期", available_dates, format_func=date_label)
    data = history[selected_date]
    products = sorted(data.get("products", []), key=lambda item: int(item.get("score", 0)), reverse=True)
    query = st.text_input("搜索", placeholder="产品、场景或痛点")
    categories = sorted({p.get("category", "消费生活") for p in products})
    category = st.radio("领域", ["全部"] + categories)
    favorites_only = st.toggle("只看我的收藏", disabled=not auth.is_logged_in())
    st.divider()
    st.caption(f"最近更新：{data.get('updated_at', '尚未更新')}")
    st.caption(f"候选来源：{data.get('candidate_count', 0)} 条")

keys = [product_key(item) for item in products]
my_favorites, favorite_counts = auth.favorite_state(keys)

filtered = []
for product in products:
    key = product_key(product)
    haystack = json.dumps(product, ensure_ascii=False).lower()
    if query and query.lower() not in haystack:
        continue
    if category != "全部" and product.get("category") != category:
        continue
    if favorites_only and key not in my_favorites:
        continue
    filtered.append(product)

st.markdown(
    f"""<div class="hero"><div class="eyebrow"><span class="pulse"></span>DAILY SIGNAL · {safe(selected_date)}</div>
    <h1>中国 AI <span>产品发现榜</span></h1>
    <p>收录当日所有达到入榜标准的具体 AI 产品，按新鲜度、热度、创新性与场景价值综合排序。</p></div>""",
    unsafe_allow_html=True,
)

metric_values = [len(products), len(categories), data.get("source_count", 0)]
metric_labels = ["当日入选", "核心领域", "资讯来源"]
metric_html = "".join(
    f'<div class="metric"><b>{value}</b><span>{label}</span></div>'
    for value, label in zip(metric_values, metric_labels)
)
st.markdown(f'<div class="metrics">{metric_html}</div>', unsafe_allow_html=True)

st.write("")

@st.dialog("产品深度情报", width="large")
def show_detail(product: dict) -> None:
    header_left, header_right = st.columns([1, 6], vertical_alignment="center")
    with header_left:
        logo_path = product.get("logo_path", "")
        if logo_path and (ROOT / logo_path).exists():
            st.image(str(ROOT / logo_path), width=64)
    with header_right:
        st.markdown(f"## {product.get('name', '')}")
        st.caption(f"{product.get('category', '')} · 榜单分 {product.get('score', 0)} · {product.get('launch_date', selected_date)}")
    st.markdown(product.get("summary", ""))
    if product.get("official_url"):
        label = product.get("official_link_label", "访问产品官网")
        st.link_button(f"{label} ↗", product["official_url"], use_container_width=True)
    fields = [
        ("定位", "positioning"), ("核心痛点", "pain_points"), ("产品解法", "solution"),
        ("产品设计思路", "design"), ("产品如何实现", "implementation"),
        ("商业价值", "business_value"), ("深度反思", "reflection"), ("用户反馈", "user_feedback"),
    ]
    analysis = product.get("analysis", {})
    for title, key in fields:
        st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
        value = analysis.get(key, "暂无可靠信息")
        if isinstance(value, list):
            for item in value:
                st.markdown(f"- {item}")
        else:
            st.markdown(f'<div class="detail-copy">{safe(value)}</div>', unsafe_allow_html=True)
    if product.get("sources"):
        st.markdown('<div class="section-title">信息来源</div>', unsafe_allow_html=True)
        for source in product["sources"]:
            st.markdown(f"- [{source.get('title', '原始报道')}]({source.get('url', '#')})")


previous_product_count = st.session_state.get("_rendered_product_count", 0)
slot_count = max(len(filtered), previous_product_count)
with st.container(key="product-results"):
    empty_message = st.empty()
    if not filtered:
        empty_message.info("没有匹配的产品。")

    for slot_index in range(slot_count):
        slot = st.empty()
        if slot_index >= len(filtered):
            slot.empty()
            continue

        product = filtered[slot_index]
        index = slot_index + 1
        with slot.container():
            key = product_key(product)
            card, actions = st.columns([8.5, 1.5], vertical_alignment="center")
            with card:
                tags = "".join(f'<span class="chip">{safe(tag)}</span>' for tag in product.get("tags", [])[:4])
                top = " top" if index <= 3 else ""
                st.markdown(
                    f"""<div class="product"><div class="rank{top}">{index:02d}</div>{logo_html(product)}<div>
                    <h3>{safe(product.get('name', ''))}</h3><p>{safe(product.get('summary', ''))}</p><div class="chips"><span class="chip">{safe(product.get('category', ''))}</span>{tags}</div>
                    </div><div class="score"><strong>▲ {safe(product.get('score', 0))}</strong><small>signal score</small></div></div>""",
                    unsafe_allow_html=True,
                )
            with actions:
                if st.button("查看", key=f"view-{selected_date}-{key}", use_container_width=True):
                    show_detail(product)
                active = key in my_favorites
                star_label = f"{'★' if active else '☆'} {favorite_counts.get(key, 0)}"
                if st.button(star_label, key=f"star-{selected_date}-{key}", use_container_width=True, help="收藏产品"):
                    ok, message = auth.set_favorite(key, selected_date, not active)
                    if ok:
                        st.rerun()
                    else:
                        st.toast(message)

    st.caption("AI 分析用于产品研究，不替代官方说明；无法核实的信息会保留为待验证。")

st.session_state["_rendered_product_count"] = len(filtered)
