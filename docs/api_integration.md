# 平台接入指南

把 Mock 工具替换为真实 API 的完整路径。每节包含：可用方案、鉴权方式、限流、成本、代码改动位置。

---

## 已开箱即用（无需付费/auth）

### Google Trends
```bash
pip install pytrends
```
- **数据**：实时热度趋势、相关上升话题
- **限制**：非官方库，密集请求会触发 429。建议每次调用间隔 ≥3s
- **代码位置**：`scenarios/tools_real.py` → `_get_google_trends`
- **场景**：海外品牌监控、跨境内容选题、英文热点追踪

### HackerNews
- **数据**：科技/创业热门帖子、评分、评论数
- **接口**：`https://hacker-news.firebaseio.com/v0/topstories.json`
- **限制**：实质无限流
- **代码位置**：`scenarios/tools_real.py` → `_get_hackernews_top`
- **场景**：科技品牌内容选题、趋势监控

### 微博热搜（第三方聚合）
- **接口**：`https://api.vvhan.com/api/hotlist/wbHot`（公开镜像）
- **限制**：第三方维护，稳定性不保证；高频会被限
- **生产替换**：见下文「微博官方/付费方案」
- **代码位置**：`scenarios/tools_real.py` → `_get_weibo_hot`

---

## 国内主流社媒（需第三方付费服务）

### 小红书

官方无开放 API。三种实际可行的路径：

| 方案 | 说明 | 成本 | 适用 |
|---|---|---|---|
| 新红数据 (xinhong.com) | 笔记搜索/达人分析/品牌监测 API | 起步约 ¥6000/年 | 中小品牌方 |
| 千瓜数据 (qian-gua.com) | 商业版 API，覆盖更全 | 起步约 ¥1.2w/年 | 中大型品牌 |
| 灰豚数据 | 含 KOL 报价、笔记舆情 | 按调用计费 | 灵活预算 |

**接入步骤**：
1. 申请商家账号，获取 API Key
2. 在 `.env` 添加 `XINHONG_API_KEY=...`
3. 在 `scenarios/tools_real.py` 新增 `_get_xiaohongshu_posts`，参考 `_get_hackernews_top` 结构
4. 在 `scenario_registry.json` 对应场景的 `tools` 字段加入新工具名

代码骨架：
```python
def _get_xiaohongshu_posts(brand: str, days: int = 7) -> str:
    import requests, os
    r = requests.get(
        "https://api.xinhong.com/v1/notes/search",
        headers={"Authorization": f"Bearer {os.getenv('XINHONG_API_KEY')}"},
        params={"keyword": brand, "days": days},
        timeout=15,
    )
    r.raise_for_status()
    return json.dumps({
        "source": "xinhong_api",
        "snapshot_at": datetime.now().isoformat(timespec="seconds"),
        "items": r.json().get("data", []),
    }, ensure_ascii=False)
```

### 抖音

官方有「巨量算数开放平台」但门槛高（企业/MCN 资质）。常用第三方：

| 方案 | 说明 | 成本 |
|---|---|---|
| 飞瓜数据 (feigua.cn) | 抖音视频/达人/直播分析 | ¥3000-2w/年 |
| 蝉妈妈 (chanmama.com) | 电商类抖音监控 | ¥6000+/年 |
| 巨量引擎官方 API | 需广告主资质 | 按消耗计费 |

接入方式同小红书，调用第三方 REST API。

### 微博（官方）

- **官方开放平台**：`https://open.weibo.com`
- **免费 OAuth2 接入**：仅支持自有账号读写
- **企业 API**：需企业认证，价格协商
- **第三方付费**：新浪舆情通（含全网舆情）、知微、清博

---

## 飞书推送（实际可用，已有 mock）

把 `v3_agent/tools.py` 中的 `send_feishu_report` mock 替换为真实调用：

```python
import requests, os, json

def send_feishu_report(threat_level, summary, key_findings, recommended_actions):
    color_map = {"high": "red", "medium": "orange", "low": "green"}
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "竞品监控报告"},
                "template": color_map.get(threat_level, "blue"),
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": summary}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": "**关键发现**\n" + "\n".join(f"- {f}" for f in key_findings)}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": "**建议行动**\n" + "\n".join(f"- {a}" for a in recommended_actions)}},
            ],
        },
    }
    r = requests.post(os.getenv("FEISHU_WEBHOOK"), json=card, timeout=10)
    return json.dumps({"sent": r.json()}, ensure_ascii=False)
```

`.env` 添加：
```
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx
```

获取 webhook：飞书群 → 设置 → 群机器人 → 添加自定义机器人。

---

## 邮件发送（SMTP）

替换 `scenarios/tools_extended.py` 的 `_send_email_report`：

```python
import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def _send_email_report(to: str, subject: str, body: str) -> str:
    msg = MIMEMultipart()
    msg["From"]    = os.getenv("SMTP_USER")
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 465))) as s:
        s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
        s.send_message(msg)
    return json.dumps({"sent_to": to, "subject": subject})
```

`.env`：
```
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=youraddr@qq.com
SMTP_PASS=授权码（不是登录密码）
```

---

## LLM 平台（已抽象，仅改 .env）

`framework/llm_client.py` 已封装五个平台，业务代码无需改动。

| Provider | 模型示例 | 注册地址 | 特点 |
|---|---|---|---|
| openai | gpt-4o-mini | platform.openai.com | 国内需代理 |
| anthropic | claude-haiku-4-5 | console.anthropic.com | 长文档强 |
| deepseek | deepseek-chat | platform.deepseek.com | 国内首选，¥0.001/千 token |
| moonshot | moonshot-v1-8k | platform.moonshot.cn | Kimi，长上下文 |
| zhipu | glm-4-flash | open.bigmodel.cn | 有免费额度 |

---

## 添加新工具的标准流程

1. 在 `scenarios/tools_real.py`（或新建 `tools_xxx.py`）写 `_my_tool` 函数，返回 JSON 字符串
2. 在同文件 `REAL_TOOLS` 列表中加 OpenAI Function Calling schema
3. 在 `execute_real_tool` 的 `handlers` 字典里登记
4. 在 `framework/scenario_registry.json` 的对应场景 `tools` 字段中加入工具名
5. 跑一次 `python run.py "测试任务"` 验证

`agent_runner._load_tools` 会自动把 `tools_real.py` 接进路由表，无需改框架代码。

---

## 限流与错误处理

所有真实 API 工具：
- 必须设置 `timeout`
- 必须捕获异常并返回 `{"error": "..."}`，不要抛出
- 高频调用需在工具内部做 sleep / token bucket
- 失败时 Agent 可自动降级到 Mock 工具或换用其他平台数据

---

## 成本预估（生产环境）

| 项目 | 月成本（中等使用强度） |
|---|---|
| LLM (DeepSeek) | ¥50-200 |
| LLM (GPT-4o-mini) | $20-80 |
| 小红书数据（新红 API） | ¥500-2000 |
| 抖音数据（飞瓜） | ¥300-1500 |
| 飞书 / 邮件 | ¥0 |
| **合计（国内场景）** | **¥1000-4000/月** |

替代单人 0.5 FTE 的执行工时，ROI 在第一个月就能算清。
