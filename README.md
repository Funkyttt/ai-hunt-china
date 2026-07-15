# AI Hunt China

一个面向产品经理的中国 AI 新品情报站：每天发现具体场景中的 AI 产品，由 DeepSeek 输出结构化产品拆解，并在 Product Hunt 风格的网页中展示。

## 已实现

- 每天北京时间 9:00 自动采集公开资讯候选
- DeepSeek 筛选、去重、评分和八维产品分析
- 产品榜单、搜索、分类、详情和官方链接
- DeepSeek 密钥只存放在云端 Secrets，不进入代码仓库
- 采集或模型失败时不覆盖上一版有效数据
- 支持管理员在网页中手动触发更新

## 本地启动

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

只测试资讯采集，不调用 DeepSeek：

```powershell
python collector.py --dry-run
```

完整更新前，在本机环境变量中设置 `DEEPSEEK_API_KEY`。不要把真实密钥写进任何会上传到 GitHub 的文件。

## 免费上线

1. 在 GitHub 新建仓库，把本目录全部文件上传。
2. 打开 Streamlit Community Cloud，用 GitHub 登录并选择该仓库的 `app.py` 发布。
3. 在 Streamlit 应用设置的 Secrets 中加入：

```toml
DEEPSEEK_API_KEY = "sk-你的密钥"
ADMIN_PASSWORD = "你自己的管理密码"
```

4. 在 GitHub 仓库 `Settings → Secrets and variables → Actions` 中新增同名的 `DEEPSEEK_API_KEY`。
5. 打开仓库的 `Actions` 页面，手动运行一次“每日 AI 产品更新”验证。之后会在每天北京时间 9:00 自动运行。

## 工作方式

```text
公开资讯 RSS → 候选文章正文与外链 → DeepSeek 筛选 10 个产品
→ 逐个生成结构化分析 → data/products.json → Streamlit 网页
```

DeepSeek 负责理解、筛选和分析，不负责实时联网搜索。采集层与分析层分开，未来可把 RSS 发现替换成博查、Tavily、SerpAPI 或自建合规数据源。

当前默认分析模型为 `deepseek-v4-flash`，并使用非思考模式完成快速总结和结构化整理。

## MVP 边界

当前版本不需要数据库。每日数据直接保存在 GitHub 的 `data/products.json`，适合验证是否有人愿意每天看、收藏和分享这些分析。正式商业化后再加入 Supabase 或阿里云数据库、真实注册登录、收藏、评论、个性化推荐和历史榜单。
