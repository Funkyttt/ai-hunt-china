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
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "products.json"
HISTORY_DIR = ROOT / "data" / "history"
LOGO_DIR = ROOT / "assets" / "logos"
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
COARSE_CATEGORIES = {
    "企业服务": ("企业", "营销", "销售", "客服", "财务", "法务", "agent", "智能体", "自动化", "客户体验"),
    "创作设计": ("设计", "图片", "视频", "音频", "音乐", "数字人", "渲染", "cad", "创作"),
    "开发工具": ("编程", "代码", "开发", "数据库", "运维", "安全", "api", "coding"),
    "效率办公": ("办公", "文档", "会议", "助手", "协同", "招聘", "人力", "知识"),
    "行业应用": ("金融", "医疗", "教育", "工业", "制造", "农业", "政务", "建筑", "电商"),
    "消费生活": ("婚恋", "交友", "社交", "游戏", "旅行", "健身", "家庭", "个人"),
}
HISTORICAL_SEED_URLS = {
    "2026-07-06": [
        "https://www.geoaurora.cn/reports/2026-07-06-daily.html",
        "https://www.aihub.cn/news/",
    ],
    "2026-07-08": [
        "https://jishuzhan.net/article/2075087248879529985",
    ],
    "2026-07-10": [
        "https://www.izhuapp.com/index.php/2026/07/10/%E7%A7%91%E6%8A%80%E7%AE%80%E6%8A%A5%E7%AC%94%E8%AE%B02026-07-10t143443-5680800/",
    ],
    "2026-07-12": [
        "https://www.feifeixu.me/ai-daily-report",
    ],
    "2026-07-13": [
        "https://finance.sina.com.cn/stock/t/2026-07-13/doc-inihsist7377446.shtml",
        "https://view.inews.qq.com/a/20260713A07OEU00",
    ],
    "2026-07-14": [
        "https://zglg.work/ai/today/2026-07-14",
        "https://swil-news.vercel.app/news/ai-tech/2026-07-14",
    ],
    "2026-07-15": [
        "https://aifrontbrief.com/",
        "https://radarai.top/updates",
        "https://companies.caixin.com/2026-07-04/102460931.html",
    ],
}


def discover_candidates(days: int = 30, target_date: datetime | None = None) -> list[dict[str, Any]]:
    now = datetime.now(TZ_CN)
    cutoff = now - timedelta(days=days)
    target_day = target_date.date() if target_date else None
    found: dict[str, dict[str, Any]] = {}
    discovery_queries = QUERIES + (["AI新产品讯息", "AI新品日报", "AI产品上线发布"] if target_day else [])
    for query in discovery_queries:
        if target_day:
            date_phrase = f"{target_day.month}月{target_day.day}日"
            dated_query = f'"{date_phrase}" {query} {target_day.year}'
        else:
            dated_query = query
        feed_urls = [
            f"https://www.bing.com/news/search?q={quote_plus(dated_query)}&format=rss&setlang=zh-cn",
        ]
        for feed_url in feed_urls:
            feed = feedparser.parse(feed_url, request_headers={"User-Agent": UA})
            for entry in feed.entries[:20]:
                url = unwrap_url(entry.get("link", ""))
                if not url:
                    continue
                published = parse_date(entry.get("published", ""))
                if target_day and published and abs((published.date() - target_day).days) > 7:
                    continue
                if not target_day and published and published < cutoff:
                    continue
                key = canonical_key(url, entry.get("title", ""))
                found[key] = {
                    "title": clean(entry.get("title", "")),
                    "url": url,
                    "published_at": published.isoformat() if published else "",
                    "source": clean(entry.get("source", {}).get("title", "") if isinstance(entry.get("source"), dict) else ""),
                    "summary": clean(BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" "))[:500],
                    "query": dated_query,
                }
        time.sleep(0.5)
    candidates = list(found.values())
    if target_day:
        for url in HISTORICAL_SEED_URLS.get(target_day.isoformat(), []):
            key = canonical_key(url, url)
            if key not in found:
                candidates.append(
                    {
                        "title": f"{target_day.isoformat()} 定向补录资料",
                        "url": url,
                        "published_at": target_date.isoformat() if target_date else "",
                        "source": "定向核验",
                        "summary": "",
                        "query": "历史定向补录",
                    }
                )
    candidates.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return enrich_candidates(candidates[:80])


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


def choose_products(
    client: DeepSeekClient,
    candidates: list[dict[str, Any]],
    target_date: datetime | None = None,
) -> list[dict[str, Any]]:
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
    editorial_date = target_date.date() if target_date else datetime.now(TZ_CN).date()
    user = f"""榜单日期是 {editorial_date}。从候选资料中找出全部符合标准的中国AI产品，不设数量上限，也不要为了凑数加入不合格产品。
历史日期规则：只有证据明确表明产品在榜单当日发布、上线或完成重要更新时才能入榜；报道可以晚于榜单日期，但不能仅因报道发布在附近日期就推断产品日期。
入榜标准：必须是具体可使用产品或明确产品功能更新；有中国团队或主要面向中国市场；有可追溯证据；综合评分不低于60分。排除基础模型、融资、战略、纯概念和重复产品。
按新鲜度30%、讨论热度25%、产品创新25%、场景明确度20%打0-100分。相同产品去重。
candidate_indexes 必须直接复制候选资料中的 index，至少包含一个编号。
输出格式：{{"products":[{{"name":"","category":"","score":0,"candidate_indexes":[0],"reason":""}}]}}。
候选资料：{json.dumps(compact, ensure_ascii=False)}"""
    selected = client.json(system, user, max_tokens=6000).get("products", [])
    merged: dict[str, dict[str, Any]] = {}
    for item in selected:
        name = clean(str(item.get("name", ""))).lower()
        try:
            score = int(item.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        if name and score >= 60 and name not in merged:
            merged[name] = item
    selected = sorted(merged.values(), key=lambda item: int(item.get("score", 0)), reverse=True)
    result = []
    for product in selected:
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
        product["score"] = max(0, min(100, score))
        product["evidence"] = [candidates[i] for i in indexes[:4]]
        result.append(product)
    if not result:
        raise RuntimeError("没有筛选出符合60分门槛且证据完整的具体产品。")
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


def coarse_category(product: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(product.get("name", "")),
            str(product.get("category", "")),
            str(product.get("summary", "")),
            " ".join(str(tag) for tag in product.get("tags", [])),
        ]
    ).lower()
    strong_vertical = COARSE_CATEGORIES["行业应用"]
    if any(keyword in text for keyword in strong_vertical):
        return "行业应用"
    strong_consumer = COARSE_CATEGORIES["消费生活"]
    if any(keyword in text for keyword in strong_consumer):
        return "消费生活"
    scores = {
        category: sum(text.count(keyword) for keyword in keywords)
        for category, keywords in COARSE_CATEGORIES.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "消费生活"


def cache_product_logo(product: dict[str, Any]) -> str:
    page_url = product.get("official_url", "")
    if not page_url or product.get("official_link_label") != "访问产品官网":
        return ""
    try:
        response = requests.get(page_url, headers={"User-Agent": UA}, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        candidates: list[str] = []
        for selector, attribute in (
            ('meta[property="og:image"]', "content"),
            ('meta[name="twitter:image"]', "content"),
            ('link[rel~="apple-touch-icon"]', "href"),
            ('link[rel~="icon"]', "href"),
        ):
            node = soup.select_one(selector)
            if node and node.get(attribute):
                candidates.append(urljoin(page_url, node.get(attribute)))
        candidates.append(urljoin(page_url, "/favicon.ico"))
        for candidate in candidates:
            try:
                image_response = requests.get(candidate, headers={"User-Agent": UA}, timeout=12)
                image_response.raise_for_status()
                content_type = image_response.headers.get("Content-Type", "").split(";")[0].lower()
                if not content_type.startswith("image/") or len(image_response.content) > 3_000_000:
                    continue
                extension = {
                    "image/png": ".png",
                    "image/jpeg": ".jpg",
                    "image/webp": ".webp",
                    "image/svg+xml": ".svg",
                    "image/x-icon": ".ico",
                    "image/vnd.microsoft.icon": ".ico",
                }.get(content_type, Path(urlparse(candidate).path).suffix.lower())
                if extension not in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"}:
                    extension = ".png"
                LOGO_DIR.mkdir(parents=True, exist_ok=True)
                for old_logo in LOGO_DIR.glob(f"{product['id']}.*"):
                    old_logo.unlink()
                logo_path = LOGO_DIR / f"{product['id']}{extension}"
                logo_path.write_bytes(image_response.content)
                return logo_path.relative_to(ROOT).as_posix()
            except requests.RequestException:
                continue
    except requests.RequestException:
        return ""
    return ""


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
    product["category"] = coarse_category(product)
    product["sources"] = [
        {"title": item.get("title", "原始报道"), "url": item.get("url", ""), "source": item.get("source", "")}
        for item in selected.get("evidence", [])
    ]
    product["logo_path"] = cache_product_logo(product)
    return product


def run_pipeline(dry_run: bool = False, target_date: datetime | None = None) -> dict[str, Any]:
    client = None if dry_run else DeepSeekClient()
    candidates = discover_candidates(target_date=target_date)
    if dry_run:
        print(json.dumps(candidates[:5], ensure_ascii=False, indent=2))
        return {"candidate_count": len(candidates)}
    if not candidates:
        raise RuntimeError("没有采集到候选信息，现有榜单保持不变。")
    assert client is not None
    selected = choose_products(client, candidates, target_date=target_date)
    if not selected:
        raise RuntimeError("DeepSeek 未筛选出合格产品，现有榜单保持不变。")
    with ThreadPoolExecutor(max_workers=3) as pool:
        products = list(pool.map(lambda item: analyze_product(client, item), selected))
    now = datetime.now(TZ_CN)
    editorial_date = target_date.date() if target_date else now.date()
    payload = {
        "date": editorial_date.isoformat(),
        "updated_at": now.isoformat(timespec="minutes"),
        "candidate_count": len(candidates),
        "source_count": len({urlparse(c["url"]).netloc for c in candidates}),
        "products": products,
    }
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_file = HISTORY_DIR / f"{editorial_date.isoformat()}.json"
    temp = history_file.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(history_file)
    if not target_date or editorial_date >= datetime.now(TZ_CN).date():
        DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def refresh_existing_logos() -> int:
    files = sorted(HISTORY_DIR.glob("*.json")) if HISTORY_DIR.exists() else []
    if DATA_FILE.exists() and DATA_FILE not in files:
        files.append(DATA_FILE)
    updated = 0
    for data_file in files:
        payload = json.loads(data_file.read_text(encoding="utf-8"))
        changed = False
        for product in payload.get("products", []):
            category = coarse_category(product)
            if product.get("category") != category:
                product["category"] = category
                changed = True
            logo_path = cache_product_logo(product)
            if logo_path and product.get("logo_path") != logo_path:
                product["logo_path"] = logo_path
                changed = True
        if changed:
            data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            updated += 1
    return updated


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
    parser.add_argument("--date", help="生成指定日期榜单，格式 YYYY-MM-DD")
    parser.add_argument("--refresh-logos", action="store_true", help="为现有榜单刷新官网 Logo")
    args = parser.parse_args()
    try:
        if args.refresh_logos:
            updated_files = refresh_existing_logos()
            print(f"Logo 刷新完成：更新 {updated_files} 个数据文件。")
            raise SystemExit(0)
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=TZ_CN) if args.date else None
        result = run_pipeline(dry_run=args.dry_run, target_date=target)
        product_count = len(result.get("products", []))
        if not args.dry_run:
            write_status("success", "每日采集与分析完成", product_count)
        print(f"完成：{result.get('candidate_count', 0)} 条候选，{product_count} 个产品。")
    except Exception as exc:
        write_status("failed", f"{type(exc).__name__}: {exc}")
        raise
