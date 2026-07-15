from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "products.json"
STATUS_FILE = ROOT / "data" / "update_status.json"
TZ_CN = timezone(timedelta(hours=8))
UA = "AIHuntChina/1.0 (+product-research; respectful single-pass crawler)"
QUERIES = [
    "中国 AI 产品 发布 工具",
    "国产 AI 应用 上线 新产品",
    "AI Agent 产品 发布 国内",
    "AI 设计 电商 教育 办公 产品 发布",
    "AI 视频 数字人 编程 营销 新品",
    "国内 AI 创业 产品 发布",
    "AI 助手 上线",
    "智能体 产品 发布 国内",
    "AI 应用 发布 国内",
    "人工智能 产品 上线 中国",
]
NON_OFFICIAL_HOSTS = {
    "bing.com", "baidu.com", "zhihu.com", "sohu.com", "36kr.com", "qq.com",
    "sina.com.cn", "msn.com", "pedaily.cn", "toutiao.com", "163.com",
}
VERIFIED_OFFICIAL_URLS = {
    "微信小微": "https://weixin.qq.com/",
    "workbuddy": "https://www.workbuddy.ai/",
    "laiye worker": "https://laiye.com/news/",
    "aipy企业版": "https://www.aipyaipy.com/companies/",
    "deep code": "https://deepcode.vegamo.cn/",
    "秒悟meoo night plan": "https://meoo.com/",
    "豆包": "https://www.doubao.com/",
    "hy3正式版": "https://github.com/Tencent-Hunyuan/Hy3",
    "hy3": "https://github.com/Tencent-Hunyuan/Hy3",
    "qoder企业版": "https://qoder.com/",
    "mk-claw": "https://www.landray.com.cn/",
    "浩辰ai设计智能体": "https://www.gstarcad.com.cn/",
    "databridge agent": "https://help.aliyun.com/zh/dts/user-guide/what-is-databridge-agent",
    "腾讯ai双引擎防沉迷": "https://jiazhang.qq.com/",
    "liblib ai": "https://www.liblib.art/",
    "revor ai": "https://revor.ai/",
    "acx": "https://laiye.com/product/acx-intro",
    "浩辰ai识图": "https://www.gstarcad.com/",
    "gstarrender": "https://www.gstarcad.com/ai/render/",
}


def discover_candidates(days: int = 30) -> list[dict[str, Any]]:
    now = datetime.now(TZ_CN)
    cutoff = now - timedelta(days=days)
    found: dict[str, dict[str, Any]] = {}
    for query in QUERIES:
        feed_urls = [
            f"https://www.bing.com/news/search?q={quote_plus(query)}&format=rss&setlang=zh-cn",
        ]
        for feed_url in feed_urls:
            feed = feedparser.parse(feed_url, request_headers={"User-Agent": UA})
            for entry in feed.entries[:20]:
                url = unwrap_url(entry.get("link", ""))
                if not url:
                    continue
                published = parse_date(entry.get("published", ""))
                if published and published < cutoff:
                    continue
                key = canonical_key(url, entry.get("title", ""))
                found[key] = {
                    "title": clean(entry.get("title", "")),
                    "url": url,
                    "published_at": published.isoformat() if published else "",
                    "source": clean(entry.get("source", {}).get("title", "") if isinstance(entry.get("source"), dict) else ""),
                    "summary": clean(BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" "))[:500],
                    "query": query,
                }
        time.sleep(0.5)
    candidates = list(found.values())
    candidates.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return enrich_candidates(candidates[:45])


def unwrap_url(url: str) -> str:
    parsed = urlparse(url)
    if "bing.com" in parsed.netloc:
        params = parse_qs(parsed.query)
        for key in ("url", "u"):
            if params.get(key) and params[key][0].startswith("http"):
                return params[key][0]
    return url


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = date_parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ_CN)
    except (ValueError, TypeError, OverflowError):
        return None


def canonical_key(url: str, title: str) -> str:
    parsed = urlparse(url)
    raw = f"{parsed.netloc}{parsed.path}|{re.sub(r'\W+', '', title)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def clean(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def enrich_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def enrich(item: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.get(item["url"], headers={"User-Agent": UA}, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            for node in soup(["script", "style", "nav", "footer", "aside"]):
                node.decompose()
            item["article_text"] = clean(soup.get_text(" "))[:4500]
            host = urlparse(item["url"]).netloc
            links = []
            for anchor in soup.select("a[href]"):
                href = anchor.get("href", "")
                target = urlparse(href)
                if target.scheme in {"http", "https"} and target.netloc and target.netloc != host:
                    links.append({"text": clean(anchor.get_text(" "))[:60], "url": href})
            item["outbound_links"] = links[:20]
        except requests.RequestException:
            item["article_text"] = ""
            item["outbound_links"] = []
        return item

    with ThreadPoolExecutor(max_workers=5) as pool:
        return list(pool.map(enrich, candidates))


class DeepSeekClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        if not self.api_key:
            raise RuntimeError("缺少 DEEPSEEK_API_KEY，未调用模型，也不会覆盖现有数据。")

    def json(self, system: str, user: str, max_tokens: int = 5000) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=180,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)
            except (requests.RequestException, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"DeepSeek 调用失败：{last_error}")


def choose_products(client: DeepSeekClient, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for index, item in enumerate(candidates):
        compact.append(
            {
                "index": index,
                "title": item.get("title"),
                "url": item.get("url"),
                "published_at": item.get("published_at"),
                "source": item.get("source"),
                "summary": item.get("summary"),
                "article_excerpt": item.get("article_text", "")[:3500],
                "outbound_links": item.get("outbound_links", [])[:8],
            }
        )
    system = """你是中国 AI 产品研究主编。只筛选具体场景中的可使用产品或明确功能更新，排除基础模型、泛行业新闻、融资新闻和纯概念。严格依据证据，不得编造产品名、发布日期或官网。输出合法 JSON。"""
    user = f"""今天是 {datetime.now(TZ_CN).date()}。从候选资料中选出5至10个近期发布、具体、有趣且具产品研究价值的中国AI产品；如果确有不足可以少于5个，但不要因为资料不完美而全部放弃。
按新鲜度30%、讨论热度25%、产品创新25%、场景明确度20%打0-100分。相同产品去重。
candidate_indexes 必须直接复制候选资料中的 index，至少包含一个编号。
输出格式：{{"products":[{{"name":"","category":"","score":0,"candidate_indexes":[0],"reason":""}}]}}。
候选资料：{json.dumps(compact, ensure_ascii=False)}"""
    selected = client.json(system, user, max_tokens=3500).get("products", [])
    if len(selected) < 10:
        supplement_system = """你是AI产品情报编辑。请从证据中提取具体产品，不要把公司、模型、行业或战略当作产品。一篇报道可拆出多个独立产品。输出合法JSON，不得编造证据编号。"""
        supplement_user = f"""从下面候选资料中补充提取具体的中国AI产品或明确的产品功能更新，目标是凑满10个不同产品动态。
已有产品名：{json.dumps([item.get('name') for item in selected], ensure_ascii=False)}
每个产品必须给出证据编号 candidate_indexes。输出格式：{{"products":[{{"name":"","category":"","score":0,"candidate_indexes":[0],"reason":""}}]}}。
候选资料：{json.dumps(compact, ensure_ascii=False)}"""
        supplements = client.json(supplement_system, supplement_user, max_tokens=4000).get("products", [])
        merged: dict[str, dict[str, Any]] = {}
        for item in selected + supplements:
            name = clean(str(item.get("name", ""))).lower()
            if name and name not in merged:
                merged[name] = item
        selected = list(merged.values())[:10]
    result = []
    for product in selected[:10]:
        indexes = []
        for value in product.get("candidate_indexes", []):
            try:
                index = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(candidates):
                indexes.append(index)
        if not indexes and product.get("name"):
            name = clean(product["name"]).lower()
            indexes = [
                index for index, candidate in enumerate(candidates)
                if name in candidate.get("title", "").lower()
            ][:2]
        if not indexes:
            continue
        try:
            score = int(product.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        if score <= 0:
            # Supplemental selections are already ranked; preserve that order when
            # the model omits a numeric score instead of showing a misleading zero.
            score = max(60, 78 - len(result) * 2)
        product["score"] = max(0, min(100, score))
        product["evidence"] = [candidates[i] for i in indexes[:4]]
        result.append(product)
    if len(result) < 10:
        raise RuntimeError(f"仅筛选出 {len(result)} 个有证据的具体产品，未达到每日10个的发布标准。")
    return result


def official_search_results(product_name: str) -> list[dict[str, str]]:
    query = quote_plus(f'"{product_name}" 官网 官方')
    feed = feedparser.parse(
        f"https://www.bing.com/search?q={query}&format=rss&setlang=zh-cn",
        request_headers={"User-Agent": UA},
    )
    results = []
    for entry in feed.entries[:8]:
        url = unwrap_url(entry.get("link", ""))
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if not url or any(host == blocked or host.endswith(f".{blocked}") for blocked in NON_OFFICIAL_HOSTS):
            continue
        results.append({"title": clean(entry.get("title", "")), "url": url})
    return results[:5]


def analyze_product(client: DeepSeekClient, selected: dict[str, Any]) -> dict[str, Any]:
    system = """你是资深AI产品经理和事实核查编辑。依据给定资料做产品拆解；事实与推断必须分开，证据不足时写“待验证”，绝不虚构用户评价、技术架构、价格或官网。输出合法JSON，不要Markdown。"""
    schema = """{
      "name":"", "slug":"英文短标识", "category":"", "summary":"50字内",
      "official_url":"仅从资料中的明确官网链接选择，无法确认则为空", "launch_date":"YYYY-MM-DD或待验证",
      "tags":[""], "analysis":{
        "positioning":"", "pain_points":[""], "solution":[""], "design":[""],
        "implementation":["可验证事实或标注为合理推测"], "business_value":[""],
        "reflection":[""], "user_feedback":["真实反馈；没有证据则明确写暂无可核实反馈"]
      }
    }"""
    official_candidates = official_search_results(selected.get("name", ""))
    user = f"""拆解产品：{selected.get('name')}。评分：{selected.get('score')}。
返回以下JSON结构：{schema}
官网搜索候选：{json.dumps(official_candidates, ensure_ascii=False)}
优先从官网搜索候选中选择与产品名和公司明确对应的 official_url；无法确认时仍应留空，不要猜测。
资料：{json.dumps(selected.get('evidence', []), ensure_ascii=False)}"""
    product = client.json(system, user)
    product["score"] = max(0, min(100, int(selected.get("score", 0))))
    trusted_url = VERIFIED_OFFICIAL_URLS.get(clean(product.get("name", "")).lower())
    if trusted_url:
        product["official_url"] = trusted_url
    if product.get("official_url"):
        product["official_link_label"] = "访问产品官网"
    else:
        release_url = next(
            (item.get("url") for item in selected.get("evidence", []) if item.get("url")),
            "",
        )
        product["official_url"] = release_url
        product["official_link_label"] = "查看产品发布页"
    product["id"] = product.get("slug") or hashlib.sha1(product.get("name", "product").encode()).hexdigest()[:10]
    product["sources"] = [
        {"title": item.get("title", "原始报道"), "url": item.get("url", ""), "source": item.get("source", "")}
        for item in selected.get("evidence", [])
    ]
    return product


def run_pipeline(dry_run: bool = False) -> dict[str, Any]:
    client = None if dry_run else DeepSeekClient()
    candidates = discover_candidates()
    if dry_run:
        print(json.dumps(candidates[:5], ensure_ascii=False, indent=2))
        return {"candidate_count": len(candidates)}
    if not candidates:
        raise RuntimeError("没有采集到候选信息，现有榜单保持不变。")
    assert client is not None
    selected = choose_products(client, candidates)
    if not selected:
        raise RuntimeError("DeepSeek 未筛选出合格产品，现有榜单保持不变。")
    products = []
    for item in selected:
        products.append(analyze_product(client, item))
    now = datetime.now(TZ_CN)
    payload = {
        "date": now.date().isoformat(),
        "updated_at": now.isoformat(timespec="minutes"),
        "candidate_count": len(candidates),
        "source_count": len({urlparse(c["url"]).netloc for c in candidates}),
        "products": products,
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = DATA_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(DATA_FILE)
    return payload


def write_status(status: str, message: str, product_count: int = 0) -> None:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    safe_message = (message or "").replace(api_key, "[REDACTED]") if api_key else (message or "")
    payload = {
        "status": status,
        "updated_at": datetime.now(TZ_CN).isoformat(timespec="seconds"),
        "message": safe_message[:1200],
        "product_count": product_count,
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    }
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只测试公开资讯采集，不调用 DeepSeek")
    args = parser.parse_args()
    try:
        result = run_pipeline(dry_run=args.dry_run)
        product_count = len(result.get("products", []))
        if not args.dry_run:
            write_status("success", "每日采集与分析完成", product_count)
        print(f"完成：{result.get('candidate_count', 0)} 条候选，{product_count} 个产品。")
    except Exception as exc:
        write_status("failed", f"{type(exc).__name__}: {exc}")
        raise
