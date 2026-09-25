---
name: sycm-backend-data-mining
version: 1.0.0
display_name: 生意参谋后台取数
display_name_en: Sycm Backend Data Mining
description: |
  从淘宝/天猫「生意参谋」后台实抓经营数据（流量来源、访客分布、时段分布、
  地域分布、人群画像、搜索词、商品排行等），用于电商诊断、推广决策与报表。
  当用户要求"看店铺数据/分析某商品流量/拉推广数据/人群画像/分时段地域"
  且本机浏览器已登录生意参谋时使用。也覆盖「图表只有图没有数字表」时
  如何把数据从 SVG 里反算出来。
description_zh: 从淘宝/天猫「生意参谋」后台实抓经营数据，覆盖流量来源、访客分布、时段分布、地域分布、人群画像、搜索词、商品排行等页面，用于电商诊断、推广决策与报表生成。当用户要求"看店铺数据/分析某商品流量/拉推广数据/人群画像/分时段地域"且本机浏览器已登录生意参谋时使用。也覆盖「图表只有图没有数字表」时如何把数据从 SVG 里反算出来。含后台路由表（不要猜 URL，猜必 404）、bsk 会话建立与复用、结构化取数的定位纪律，以及抓不到时的降级写法。
description_en: Scrape real operating data from the Taobao/Tmall Sycm merchant backend, covering traffic sources, visitor distribution, hour-of-day and regional breakdowns, audience profiles, search terms and item rankings, for e-commerce diagnosis, ad decisions and report generation. Use when the user asks to look at store data, analyse an item's traffic, pull ad data, build audience profiles, or break results down by region and hour, and the local browser is already signed in to Sycm. Also covers recovering numbers from SVG-only charts when a page has no data table. Ships the backend route table, bsk session setup and reuse, structural value-locating rules, and the fallback wording to use when a figure cannot be scraped.
license: MIT
compatibility: Requires Python 3.9+ and browser automation (bsk CLI); data is scraped from a logged-in Sycm merchant backend. Runs on WorkBuddy and Codex.
agent_created: true
---

# 生意参谋后台取数

## 前置条件

- 本机 Chrome 已登录该店铺的生意参谋（`sycm.taobao.com`，账号显示为「<店铺名> 主店」）。
- bsk 浏览器自动化可用。**若 `bsk` 命令静默失败/无输出/SIGTERM，先走 `bsk-browser-sandbox-setup` skill**（那是个独立问题：CLI 与扩展版本错配，或沙箱回收了 daemon）。

## 第 0 步：建会话（一次建好，后续命令复用）

```bash
# 不要把本机绝对路径写进技能文件（含用户名的路径换机即失效）。
# 用姊妹技能的解析器：它会在运行期探测真 bash / python / bsk / BSK_HOME。
CE_ENV="$HOME/.codex/skills/sycm-ops-daily-report/scripts/codex_env.sh"   # Codex
# CE_ENV="$HOME/.workbuddy/skills/sycm-ops-daily-report/scripts/codex_env.sh"  # WorkBuddy
. "$CE_ENV"

SID=$("$CE_BSK_EXE" session start --json 2>/dev/null | "$CE_PY" -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
```

后续所有命令加 `--session "$SID"`。**daemon 必须常驻**（详见 sandbox skill），否则每条命令结束会话就没了。

> **Codex 端**：不要手搓上面的命令，直接用
> `sycm-ops-daily-report\scripts\bsk_grab.ps1`（一次命令跑完一个页面）或 `bsk_check.ps1`（环境自检）。

## 路由表 —— 不要猜 URL，猜必 404

| 页面 | URL |
|---|---|
| 首页 | `https://sycm.taobao.com/portal/home.htm` |
| 交易 | `https://sycm.taobao.com/ipoll/index.htm` |
| 流量看板 | `https://sycm.taobao.com/flow/monitor/overview` |
| **访客分析**（时段分布 / 地域分布 / 特征分布） | `https://sycm.taobao.com/flow/visitor/analysis`　**无 `.htm` 后缀** |
| 商品排行 | `https://sycm.taobao.com/cc/item_rank` |
| 客户总览 | `https://sycm.taobao.com/cc/customer/overview` |
| 客户画像 | 从「客户」菜单点进「画像」，统计区间可切 1天/7天/30天 |
| 自助分析 | `https://sycm.taobao.com/adm/v3/micro/auto_analysis/my_space` |

**兜底做法**（比猜 URL 可靠）：先 `navigate` 到首页，再用下面这段建路由表：

```bash
"$B" evaluate "(function(){var out=[];var as=document.querySelectorAll('a');for(var i=0;i<as.length;i++){var t=(as[i].innerText||'').trim();var h=as[i].getAttribute('href')||'';if(t&&t.length<25)out.push(t+' >> '+h);}return out.join('\n');})()" --session "$SID" > "$T/links.txt" 2>&1
```

## 核心技巧：把图表数据从 SVG 里反算出来

生意参谋的趋势图/时段分布图**只有图、没有数字表格**，而且**不是 ECharts**（`window.echarts === undefined`，`getInstanceByDom` 走不通）。但它是手绘 SVG，数据就在 `path` 的 `d` 里。

### 步骤

**1. 定位目标图的 SVG** —— 用轴标签文本做锚点：

```bash
"$B" evaluate "(function(){var svgs=document.querySelectorAll('svg');var out=[];for(var i=0;i<svgs.length;i++){var s=svgs[i];if((s.textContent||'').indexOf('01:00')>-1){var tags={};var all=s.querySelectorAll('*');for(var j=0;j<all.length;j++){var t=all[j].tagName;tags[t]=(tags[t]||0)+1;}out.push('SVG'+i+' viewBox='+s.getAttribute('viewBox')+' children='+JSON.stringify(tags));}}return out.join('\n')||'nf';})()" --session "$SID"
```

判读：`path:2` = 两条折线（两条数据系列）；`rect` 很多 = 柱状图。

**2. 取 path 的 `d` 和坐标轴的 line/text**：

```bash
"$B" evaluate "(function(){var svgs=document.querySelectorAll('svg');for(var i=0;i<svgs.length;i++){var s=svgs[i];if((s.textContent||'').indexOf('01:00')>-1){var ps=[].map.call(s.querySelectorAll('path'),function(p){return p.getAttribute('d')||'';});var ls=[].map.call(s.querySelectorAll('line'),function(l){return [l.getAttribute('x1'),l.getAttribute('y1'),l.getAttribute('x2'),l.getAttribute('y2')].join(',');});var ts=[].map.call(s.querySelectorAll('text'),function(t){return ((t.textContent||'').trim())+'@'+t.getAttribute('x')+','+t.getAttribute('y');});return 'PATHS('+ps.length+'):\n'+ps.join('\n---\n')+'\n\nLINES:\n'+ls.join('\n')+'\n\nTEXTS:\n'+ts.join(' | ');}}return 'nf';})()" --session "$SID" > "$T/svgdata.txt" 2>&1
```

**3. 用 Python 换算** —— `C` 曲线每段有 3 组坐标，**最后一组是真实数据点**：

```python
import re
def pts(d):
    d=d.strip()
    m=re.match(r'M([\d.]+),([\d.]+)',d)
    out=[(float(m.group(1)),float(m.group(2)))]
    for seg in d[m.end():].split('C'):
        if not seg.strip(): continue
        nums=seg.split(',')
        out.append((float(nums[-2]),float(nums[-1])))   # 每段最后两个数 = 数据点
    return out
```

Y 轴换算：从 `text` 里拿到刻度值（如 `0/95/190/285/380`）与其 `y` 坐标（如 `270/215/160/105/50`），两点定线即可：

```python
K = (380-0)/(270-50.0)     # 每像素代表多少数值
value = (Y0 - y) * K        # Y0 = 数值 0 对应的像素 y
```

**4. 必做交叉验证** —— 页面自带的文字解读（如"近 7 天日均访客数最多的时间段为 21:00~21:59（419 人）"）是免费的校验源。**峰值时段对得上，才说明还原方法可靠**；对不上就回头检查 Y 轴刻度配对是否错位。

## 坑清单（都踩过）

| 坑 | 表现 | 处置 |
|---|---|---|
| **「AI 问数」返回演示假数据** | 问"各时段访客数"，返回 `12,345 / 23,456 / 34,567 / 45,678` 这种递增整数序列 | **该功能当前不可作数据源**。凡是"过于整齐"的数字立刻警觉，别写进报告 |
| 猜 URL | `/flow/visitor/analysis.htm` → "页面未找到" | 用上面的路由表，或抓 `<a href>` 建表 |
| 页面有内部滚动容器 | `window.scrollY` 变了，但 `screenshot` 仍捕获页面顶部 | **放弃滚动截图取数**，改抓 DOM/SVG |
| 「下载」按钮无效 | 点了没报错，但 Downloads 目录无新文件 | 别在这上面耗时间，走 SVG 反算 |
| snapshot 巨大 | 单页 500+ 行 | 存文件后 `grep -nE "关键词1|关键词2"` 定位，再 `sed -n 'a,bp'` 读区间 |
| 点击 ref 失效 | 页面重渲染后 `@eN` 指向错位 | **每次点击后必须重新 snapshot**；或直接用 JS 按文本点：`evaluate "(function(){var els=document.querySelectorAll('a,button,span,div');for(var i=0;i<els.length;i++){if((els[i].innerText||'').trim()==='目标文本'&&els[i].children.length===0){els[i].click();return 'ok';}}return 'nf';})()"` |
| 弹窗遮罩挡住点击 | 点击后 `location.href` 不变 | 先 `press Escape` 或点关闭按钮，再操作 |

## 常用数据点速查

| 想要的数据 | 去哪 |
|---|---|
| 流量来源构成 + 转化率 | 流量 → 店铺来源 / 商品来源 |
| 搜索词（引流词 / 行业相关词） | 流量 → 搜索词分析；或「市场」→ 搜索分析 |
| **时段分布 / 地域分布 / 淘气值 / 新老访客** | 流量 → **访客分析** |
| 人群画像（性别/年龄/消费层级/职业/学历/品牌偏好） | 客户 → 画像（可切"店铺客户 / 客户新访 / 未购回访 / 已购回访"） |
| 老客/会员/粉丝资产 | 客户 → 核心资产（粉丝分析 / 会员分析 / 已购客户） |
| 商品排行（支付金额/转化率） | 商品 → 商品排行 |
| 推广计划与报表 | 另开：万相台无界 `one.alimama.com` |

**访客分析的三条口径限制（实测）**：

1. **只到店铺维度，没有单品分时/地域。** 想给单品做分时/地域决策只能拿全店节律作参考（付费与自然流量人群重合度较高，尚可用），不能当单品精确值。
2. **时段分布不按星期拆分。** 工作日的午间峰值和周末的白天峰值是混在一起的，拿不到"周末 vs 工作日"的分时曲线。
3. **「时段分布解读」文案是静态的。** 切到 30 天后它仍可能显示「近 7 天日均…」，别把它当当前口径的证据；图本身会随窗口变，以图为准（并自行用 SVG 反算校验）。

**时段分布图的两条线**：`path[0]` = 访客数，`path[1]` = 下单买家数。
**注意下单线的绝对值远小于访客线**，两条线共用左侧 Y 轴；换算出来的低峰时段"转化率"会虚高——**绝对量太小的时段不要用比率下结论**。

## 输出原则

- 报告里**必须标注口径**：是"全店"还是"单品"、区间是哪几天、是否日均。生意参谋不同页面的口径经常不一致（例：流量-二级来源表的子项之和会大于汇总行，**支付金额和买家数绝不能跨行相加**）。
- 遇到系统自带的 AI 解读文案，可以拿来当**交叉验证**，但不要直接当数据引用。

## 多标签页工作流（用户常与你共用同一个浏览器）

用户在浏览器里常年开着多个页签（万相台计划详情、生意参谋搜索词分析等）。**agent 会话有自己的 Agent Window，直接操作用户的页签会报 `operation denied by the Agent Window sandbox`**。

```bash
bsk tab list --session <id>              # 列出全部页签（含 user / agent 两种 scope）
bsk tab borrow <tab-id> --session <id>   # 借用用户页签
# ... snapshot / evaluate / click ...
bsk tab return <tab-id> --session <id>   # 用完必须归还，否则用户看不到自己的页签
```

- 借用状态**容易失效**（页面重渲染或页签切换后再次操作就报同样的 sandbox 错）→ **重新 borrow 一次**即可，不是真的坏了。
- 因为 ref 失效频繁，**优先用 `evaluate` 跑 JS 按文本点击**，比按 `@eN` 点击稳得多。
- `navigate` 会自动落在 agent 自己的页签上；只有要读**用户已经打开的**页面时才需要 borrow。
- 例：读用户正开着的万相台计划详情 → `tab list` 找到 `关键词推广详情页` → borrow → 点「高级设置」看分时/地域/资源位。

## 读取后台导出的数据文件

| 格式 | 怎么读 | 说明 |
|---|---|---|
| `.xlsx` | `zipfile` 解 `xl/sharedStrings.xml` + `xl/worksheets/sheet1.xml` | 不需要 pandas |
| `.xls`（老格式） | `xlrd`（`pip install xlrd -i https://pypi.tuna.tsinghua.edu.cn/simple`） | 文件头为 `D0CF11E0`（OLE2 复合文档）即此类；**若是 HTML 伪装的 .xls，开头会是 `<html`/`<table`，要分支处理** |
| `.csv` | 直接读，编码依次试 `utf-8-sig` → `gbk` → `utf-8` | 生意参谋导出常带 BOM |

**按星期分组是分析后台日表的通用入口**：拿到逐日数据后用 `datetime.date.fromisoformat(日).weekday() >= 5` 判周末再聚合。
**必做一步：剔除最后一天** —— 生意参谋的 T+1 数据在次日早晨常未跑完（表现为访客数骤降、跳出率异常低、停留时长异常高），不剔除会严重污染结论。

**高价值报表识别**：`商品-<商品ID>-<起>_-<止>.xls`（单品 30 天逐日）是性价比最高的一份 —— 一张表同时有访客、浏览、停留、跳出率、加购、收藏、下单、支付、支付转换率、退款金额，**可直接做"周末 vs 工作日""逐日趋势"分析，不用再抠图**。
