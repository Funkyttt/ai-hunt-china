# AI Hunt China

面向产品经理的中国 AI 产品发现库。系统每天收集公开发布信息，用 DeepSeek 完成事实约束下的结构化拆解，并按日期保存榜单。

## 当前能力

- 每天北京时间 9:00 自动更新
- 所有达到 60 分入榜标准的产品全部收录，不限制 10 个
- 日期选择、六类领域筛选、全文搜索
- 自动从产品官网提取 Logo 并缓存到仓库
- 产品详情、官网或发布页、事实来源
- Supabase 邮箱注册、登录、收藏与全站收藏数

## 本地运行

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

测试采集但不调用 DeepSeek：

```powershell
python collector.py --dry-run
```

刷新现有产品 Logo 与分类：

```powershell
python collector.py --refresh-logos
```

补录指定日期：

```powershell
python collector.py --date 2026-07-01
```

## Supabase 账号与收藏

1. 创建一个 Supabase 免费项目。
2. 打开 SQL Editor，执行仓库根目录的 `supabase_schema.sql`。
3. 在 Streamlit Community Cloud 的应用设置中加入：

```toml
SUPABASE_URL = "https://你的项目.supabase.co"
SUPABASE_ANON_KEY = "你的 publishable/anon key"
```

`SUPABASE_ANON_KEY` 是前端公开密钥；不要填写 `service_role` 密钥。数据库已通过 RLS 限制用户只能新增和删除自己的收藏。

## 自动更新

GitHub Actions 的 `DEEPSEEK_API_KEY` Secret 负责云端分析。工作流会把每日数据保存到 `data/history/YYYY-MM-DD.json`，并把最新一期同步到 `data/products.json`。手动运行工作流时可填写 `target_date` 补录历史日期。

```text
公开资讯 → 候选文章与外链 → DeepSeek 全量筛选与评分
→ 产品深度分析 → 官网 Logo 缓存 → 历史榜单 → Streamlit
```

DeepSeek 密钥只存放在 GitHub Actions Secrets，不进入仓库或网页。
