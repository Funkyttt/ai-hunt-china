from __future__ import annotations

import json
import os
import subprocess
import sys
from html import escape
from datetime import datetime
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "products.json"

st.set_page_config(
    page_title="AI Hunt China",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="auto",
)


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"date": "等待首次更新", "updated_at": "", "products": []}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, os.getenv(name, default)))
    except Exception:
        return os.getenv(name, default)


def safe(value: object) -> str:
    return escape(str(value or ""), quote=True)


st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;600;700;900&display=swap');
:root { --cyan:#42e8ff; --pink:#ff4f91; --green:#66ffb5; --ink:#eef7ff; --muted:#8fa6bc; }
.stApp { background:
  radial-gradient(circle at 12% 8%, rgba(66,232,255,.12), transparent 25rem),
  radial-gradient(circle at 91% 5%, rgba(255,79,145,.13), transparent 28rem),
  linear-gradient(180deg,#050713 0%,#070b17 52%,#03050d 100%); color:var(--ink); }
.stApp, button, input { font-family:Inter,"Noto Sans SC",sans-serif; }
[data-testid="stHeader"] { background:rgba(3,5,13,.65); backdrop-filter:blur(16px); }
[data-testid="stSidebar"] { background:rgba(7,11,23,.91); border-right:1px solid rgba(66,232,255,.14); }
.block-container { max-width:1400px; padding-top:2rem; }
.brand { display:flex;align-items:center;gap:12px;font-size:14px;font-weight:800;letter-spacing:0;color:#fff; }
.brand-mark { width:34px;height:34px;display:grid;place-items:center;background:#42e8ff;color:#041019;clip-path:polygon(18% 0,100% 0,82% 100%,0 100%); }
.eyebrow { color:var(--cyan);font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:0; }
.hero { padding:18px 0 20px;border-bottom:1px solid rgba(143,166,188,.15);margin-bottom:18px; }
.hero h1 { margin:8px 0 7px;font-size:clamp(32px,5vw,64px);line-height:1.02;letter-spacing:0;font-weight:900; }
.hero h1 span { color:var(--cyan);text-shadow:0 0 28px rgba(66,232,255,.34); }
.hero p { color:var(--muted);margin:0;max-width:750px;font-size:15px; }
.pulse { display:inline-block;width:7px;height:7px;background:var(--green);border-radius:50%;box-shadow:0 0 14px var(--green);margin-right:7px; }
.product { position:relative;display:grid;grid-template-columns:70px minmax(0,1fr) auto;gap:18px;align-items:center;padding:18px 20px;margin:0 0 10px;background:rgba(11,18,34,.76);border:1px solid rgba(143,166,188,.16);border-left:2px solid transparent;transition:.2s ease;overflow:hidden; }
.product:hover { transform:translateY(-2px);border-color:rgba(66,232,255,.42);border-left-color:var(--cyan);background:rgba(14,24,43,.92);box-shadow:0 16px 50px rgba(0,0,0,.28); }
.rank { font-size:25px;font-weight:900;color:rgba(238,247,255,.34);font-variant-numeric:tabular-nums; }
.rank.top { color:var(--cyan);text-shadow:0 0 18px rgba(66,232,255,.35); }
.product h3 { margin:0 0 6px;font-size:19px;letter-spacing:0; }
.product p { margin:0;color:var(--muted);font-size:13px;line-height:1.65; }
.chips { display:flex;gap:7px;flex-wrap:wrap;margin-top:10px; }
.chip { padding:3px 8px;border:1px solid rgba(66,232,255,.21);color:#aadfe8;background:rgba(66,232,255,.06);font-size:11px; }
.score { text-align:right;min-width:88px; }
.score strong { display:block;color:var(--green);font-size:21px; }
.score small { color:var(--muted);font-size:10px;text-transform:uppercase; }
.section-title { color:var(--cyan);font-size:12px;font-weight:800;margin:22px 0 7px;text-transform:uppercase; }
.detail-copy { color:#cbd8e5;line-height:1.8;font-size:14px; }
.source { padding:11px 0;border-bottom:1px solid rgba(143,166,188,.12);font-size:12px; }
.source a { color:#afdbe5;text-decoration:none; }
.metric { padding:13px;border:1px solid rgba(143,166,188,.15);background:rgba(11,18,34,.58); }
.metric b { display:block;color:#fff;font-size:18px; }.metric span { color:var(--muted);font-size:11px; }
.stButton>button { border-radius:2px;border:1px solid rgba(66,232,255,.35);background:rgba(66,232,255,.08);color:#dffaff; }
.stButton>button:hover { border-color:var(--cyan);color:#fff;box-shadow:0 0 24px rgba(66,232,255,.15); }
@media(max-width:700px){ .product{grid-template-columns:42px minmax(0,1fr)} .score{display:none}.hero h1{font-size:38px}.block-container{padding:1rem}.product{padding:14px 12px;gap:10px} }
</style>
""",
    unsafe_allow_html=True,
)


data = load_data()
products = data.get("products", [])

with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">AI</div>HUNT CHINA</div>', unsafe_allow_html=True)
    st.caption("中国 AI 新品情报站")
    st.divider()
    query = st.text_input("搜索", placeholder="产品、场景或痛点")
    categories = sorted({p.get("category", "其他") for p in products})
    category = st.radio("领域", ["全部"] + categories)
    st.divider()
    st.caption("数据状态")
    st.markdown(f"**{data.get('date', '-')}**")
    st.caption(f"最近更新：{data.get('updated_at', '尚未更新')}")
    st.caption(f"候选来源：{data.get('candidate_count', 0)} 条")

    admin_password = secret("ADMIN_PASSWORD")
    if admin_password:
        with st.expander("管理员更新"):
            password = st.text_input("管理密码", type="password")
            if st.button("立即采集并分析", use_container_width=True):
                if password != admin_password:
                    st.error("密码不正确")
                elif not secret("DEEPSEEK_API_KEY"):
                    st.error("尚未配置 DeepSeek API Key")
                else:
                    with st.spinner("正在发现和分析今日新品，约需数分钟..."):
                        env = os.environ.copy()
                        env["DEEPSEEK_API_KEY"] = secret("DEEPSEEK_API_KEY")
                        result = subprocess.run(
                            [sys.executable, str(ROOT / "collector.py")],
                            cwd=ROOT,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=900,
                        )
                    if result.returncode == 0:
                        st.success("更新完成")
                        st.rerun()
                    else:
                        st.error(result.stderr[-800:] or "更新失败，请查看运行日志")

st.markdown(
    f"""<div class="hero"><div class="eyebrow"><span class="pulse"></span>DAILY SIGNAL · {safe(data.get('date',''))}</div>
    <h1>今日中国 AI <span>新品雷达</span></h1>
    <p>每天从公开资讯中捕捉具体场景里的新产品，再用 AI 拆解定位、痛点、解法、实现路径与商业价值。</p></div>""",
    unsafe_allow_html=True,
)

filtered = []
for product in products:
    haystack = json.dumps(product, ensure_ascii=False).lower()
    if query and query.lower() not in haystack:
        continue
    if category != "全部" and product.get("category") != category:
        continue
    filtered.append(product)

cols = st.columns(3)
for col, value, label in zip(
    cols,
    [len(products), data.get("candidate_count", 0), data.get("source_count", 0)],
    ["今日入选", "扫描候选", "资讯来源"],
):
    col.markdown(f'<div class="metric"><b>{value}</b><span>{label}</span></div>', unsafe_allow_html=True)

st.write("")
if not filtered:
    st.info("没有匹配的产品。")


@st.dialog("产品深度情报", width="large")
def show_detail(product: dict) -> None:
    st.markdown(f"## {product.get('name', '')}")
    st.caption(f"{product.get('category', '')} · 热度 {product.get('score', 0)} · {product.get('launch_date', data.get('date', ''))}")
    st.markdown(product.get("summary", ""))
    official = product.get("official_url")
    if official:
        st.link_button("访问产品官网 ↗", official, use_container_width=True)
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
    sources = product.get("sources", [])
    if sources:
        st.markdown('<div class="section-title">信息来源</div>', unsafe_allow_html=True)
        for source in sources:
            st.markdown(f"- [{source.get('title','原始报道')}]({source.get('url','#')})")


for index, product in enumerate(filtered, start=1):
    card, action = st.columns([8.8, 1.2], vertical_alignment="center")
    with card:
        tags = "".join(f'<span class="chip">{safe(tag)}</span>' for tag in product.get("tags", [])[:4])
        top = " top" if index <= 3 else ""
        st.markdown(
            f"""<div class="product"><div class="rank{top}">{index:02d}</div><div>
            <h3>{safe(product.get('name',''))}</h3><p>{safe(product.get('summary',''))}</p><div class="chips">{tags}</div>
            </div><div class="score"><strong>▲ {safe(product.get('score',0))}</strong><small>signal score</small></div></div>""",
            unsafe_allow_html=True,
        )
    with action:
        if st.button("查看", key=f"view-{product.get('id', index)}", use_container_width=True):
            show_detail(product)
        if product.get("official_url"):
            st.link_button("官网", product["official_url"], use_container_width=True)

st.caption("AI 分析用于产品研究，不替代官方说明；无法核实的信息会保留为待验证。")
