# Taobao Ops Skills · 淘系运营报表技能集

> 让 Agent 工具（WorkBuddy / Claude Code / Codex CLI / Cursor …）直连淘宝天猫后台，
> 自动产出**店铺运营日报**与**单品运营报表**，并在每条变化旁边给出**引导运营去核实的问题**。

---

## 这套技能要解决什么

大部分"AI 报表"死在同一个地方：**它给你一堆数字，但不告诉你哪里变了、更不告诉你该去问谁。**

这个仓库的所有技能都围绕一条第一性原理设计：

> **报表 = 发现变化 + 引导找到原因**

- 每条异常都配一条**问句形态**的引导（如「上周是否调整过价格或优惠券？」）
- 输出**候选因素清单**与**需人工确认清单**
- ⛔ **绝不写未经验证的"原因"** —— AI 的职责是发现变动、列出可能因素、指出该找谁确认

### 反面教材（本项目明确拒绝的写法）

| ❌ 错误 | ✅ 正确 |
|---|---|
| 「转化率下降是因为优惠券改小了」 | 「转化率下降 3.2pt。**请确认**：上周是否调整过价格 / 优惠券？竞品是否在做活动？」 |
| 「该品表现不佳，建议优化」 | 「该品访客 +42% 但转化 −1.8pt（**效率降、规模升**），承接没跟上。请查：详情页是否变更、是否有差评涌入」 |
| 抓不到就估一个数 | 抓不到就标注 **未取到**，不填估算值 |

---

## 技能清单

| 技能 | 维度 | 版本 | 说明 |
|---|---|---|---|
| [`taobao-item-ops-report`](skills/taobao-item-ops-report) | **单品** | v1.1.0 | 单个商品的运营长报告：多周期对比 + 渠道结构 + 归因闸 + 需人工确认清单，15 个板块 |
| [`sycm-ops-daily-report`](skills/sycm-ops-daily-report) | **店铺** | **v1.4.0** | 店铺运营日报：店铺/渠道/推广计划三层 + 环比对比 + 变化归因，15 个板块 |
| [`skill-frontmatter-safeedit`](skills/skill-frontmatter-safeedit) | 工具 | **v1.4.0** | 给"写技能的人"用：SKILL.md 安全编辑 + 上传前校验 + 打包复验 + 发布前敏感扫描 |

> 前两个是**业务技能**（一个看品、一个看店，互补不重叠）；第三个是**造技能的工具技能**。

---

## 核心设计原则

这套技能里最值钱的部分不是代码，是**判据**。几条有代表性的：

**① 禁止脆弱定位**
不依赖页面文本顺序、`indexOf`、固定坐标取数。必须先定位指标的**结构化容器**，再从容器内部取值。数字为真但语义归属错了，比没有数据危险十倍 —— 它不报错、不崩、看起来正常，却会让你下一个完全相反的结论。

**② 成交是滞后指标，加购是先行指标**
高客单品 / 大促蓄水期 / 养词冷启动三个场景，用成交判会**系统性误杀**，必须切到加购率 + 加购增速。

**③ 效率 × 规模 二维判读**
访客涨、转化跌 ≠ 增长。判读必须两维一起看，否则会把"承接没跟上"读成"生意变好"。

**④ 同名指标可能不同口径**
平台口径 / 自算口径 / 净口径必须分开算（如 ROI）。混用 = 结论作废。

**⑤ 趋势必须先对基准**
季节品看同比、事件品绑外部日历、稳定品才用环比。用错基准 = 系统性误杀。

**⑥ 变化必有原因，但 AI 不猜**
任何突变背后都有人为或外部动作（改价、改券、断货、竞品动手、大促节奏）。AI 列出**候选因素**，由运营去核实 —— 而不是自己编一个"原因"。

---

## 安装

### WorkBuddy

把 `skills/<技能名>/` 整个目录拷进：

```
~/.workbuddy/skills/          # 用户级，所有项目可用
<项目>/.workbuddy/skills/     # 项目级，团队共享
```

或在 WorkBuddy 的技能市场搜索「淘宝单品运营报表」「生意参谋运营日报」直接安装。

### Claude Code

```bash
cp -r skills/<技能名> ~/.claude/skills/
```

### Codex CLI

```bash
cp -r skills/<技能名> ~/.codex/skills/
```

### Cursor

```bash
cp -r skills/<技能名> ~/.cursor/skills/
```

> 以上都遵循 [Agent Skills](https://agentskills.io) 开放标准（`SKILL.md` + YAML frontmatter），
> 已被 70+ 工具采纳。Cursor 还会向后兼容 `.claude/skills` 与 `.codex/skills`。

---

## 依赖

| 依赖 | 用途 | 说明 |
|---|---|---|
| 已登录淘宝/天猫的浏览器 | 实抓生意参谋 / 万相台数据 | 技能本身**不存账号密码**，走本机登录态 |
| 浏览器自动化能力 | 页面抓取 | WorkBuddy 内置；其他工具可用 Playwright MCP / 自建 |
| Python 3.9+ | 报表渲染与自校验脚本 | 仅用标准库，无第三方依赖 |

⚠️ 抓数脚本与具体工具的浏览器能力绑定（本仓库以 WorkBuddy 为参考实现）。
换到别的 Agent 工具时，**方法论、判据、报表结构、Python 渲染脚本都可直接复用**，
只有"抓数"那一段需要按目标工具重接。

---

## 目录结构

```
taobao-ops-skills/
├── README.md
├── LICENSE
├── .gitignore
├── .gitattributes
├── .github/workflows/verify.yml   # 每次 push 自动跑发布前自检
└── skills/
    ├── taobao-item-ops-report/
    │   ├── SKILL.md                       # 主文档：总纲 / 取数铁律 / 15 段结构 / 归因闸
    │   ├── USAGE.md                       # 使用说明与原版示例
    │   ├── assets/                        # 报表模板 + 示例数据 + 示例产出
    │   ├── references/                    # 归因闸、指标与校验细则
    │   └── scripts/                       # 渲染器 + 6 项自校验
    ├── sycm-ops-daily-report/
    │   ├── SKILL.md
    │   ├── USAGE.md
    │   ├── scripts/bsk_grab.sh            # 抓数脚本（工具相关）
    │   └── templates/report_template.html
    └── skill-frontmatter-safeedit/
        ├── SKILL.md
        └── scripts/                       # 校验器 / 打包器 / 敏感扫描器
```

---

## 发布前自检（`skill-frontmatter-safeedit`）

如果你也在写技能并要发布到平台或公开仓库，这个工具技能能省下大量试错。三个零依赖脚本：

```bash
# ① 上传前校验：字段齐全 + 长度上限 + YAML 结构 + 目录名一致
python scripts/check_frontmatter.py --upload <技能目录>

# ② 打包 + 解包复验：打包前强制 LF 化，打包后复验【包内字节】
python scripts/pack_and_verify.py <技能目录> [输出.zip]

# ③ 发布前敏感扫描：店铺名 / 品牌名 / 合作方名 / 内部称呼 / 邮箱 / 手机号 / 密钥
python scripts/scan_sensitive.py <技能目录> [<技能目录2> ...]
```

**为什么需要它**：这三类问题**都不报错**，但会让上传直接失败 ——
① CRLF 游离回车破坏 YAML；② 描述字段超长被平台拒收；
③ **源目录干净 ≠ zip 干净**（打包环节可能把行尾符写回 CRLF）。
官方校验器只查 `name` / `description` 两条，会报 `valid` 却仍被平台拒收。

---

## 发布与自动化

| 产物 | 位置 | 说明 |
|---|---|---|
| **技能包（`.zip`）** | [Releases](../../releases) | 每个技能一个包，**不需要 git 也能下载** |
| 源码 | `skills/` | 直接拷进你的 skills 目录即可 |
| 自动检查 | [`.github/workflows/verify.yml`](.github/workflows/verify.yml) | 每次 push / PR 自动跑四项自检 |

### 改动技能后的本地三步（缺一不可）

```bash
# ① 字段齐全 + 长度 + 版本一致性 + 裸 CR
python skills/skill-frontmatter-safeedit/scripts/check_frontmatter.py --upload skills/<技能名>

# ② 敏感信息（店铺名 / 邮箱 / 手机号 / 密钥）—— 公开仓库必做
python skills/skill-frontmatter-safeedit/scripts/scan_sensitive.py skills/<技能名>

# ③ 打包 + 解包复验【包内字节】
python skills/skill-frontmatter-safeedit/scripts/pack_and_verify.py skills/<技能名>
```

三者都是 `0 = 通过 / 1 = 有问题` 的退出码，可直接当 CI 门禁。

### 字段：开放标准 vs WorkBuddy 扩展

`SKILL.md` 是 [Agent Skills](https://agentskills.io) 开放标准。本仓库的技能同时带两类字段：

| 字段 | 归属 | 换到 Claude Code / Codex CLI / Cursor |
|---|---|---|
| `name` / `description` | ✅ 官方标准 | **照读**，召回能力不丢 |
| `license` / `compatibility` | ✅ 官方标准（可选） | 照读 |
| `version` / `display_name` / `description_zh` / `description_en` | ⚠️ **WorkBuddy 扩展** | **静默忽略**（不报错也不生效）|

> **为什么不加官方推荐的 `metadata.version`？**
> WorkBuddy 平台要求描述字段用「单行 plain scalar」，这意味着它的解析器**可能是逐行提取**而非完整 YAML。
> 若如此，嵌套的 `  version:` 缩进行会与顶层 `version` 撞车，**直接导致上传「解析失败」**。
> 而收益极小 —— 各工具实际只读 `name` / `description` 做召回。**不为"正宗"去冒被拒的险。**

⚠️ 官方字段的硬约束（与平台实测取**更严**者）：
`name` ≤64 且**必须与目录名一致**；`description` ≤1024（平台实测更严：1000）；
`compatibility` ≤500；`license` 填许可证名。

---

## English

A set of [Agent Skills](https://agentskills.io) that pull real data from Taobao/Tmall
merchant backends (生意参谋 / 万相台) and generate **store-level daily reports** and
**single-item operation reports** as HTML.

The design principle behind every skill here:

> **A report = detect what changed + guide a human to find out why.**

Every anomaly is paired with a question-form prompt (e.g. *"Did you change the price or
coupon last week?"*), plus a list of candidate causes and a list of items requiring human
confirmation. The skills **never fabricate a cause** — the AI's job is to detect the change,
list plausible factors, and name who should verify.

Three skills:

- `taobao-item-ops-report` — per-item deep-dive report (15 sections, multi-period comparison)
- `sycm-ops-daily-report` — store-level daily report (store / channel / ad-plan layers)
- `skill-frontmatter-safeedit` — tooling for skill authors: pre-upload validation, packing
  with byte-level re-verification, and pre-publish sensitive-info scanning

Install by copying a skill folder into your agent's skills directory
(`~/.claude/skills`, `~/.codex/skills`, `~/.cursor/skills`, `~/.workbuddy/skills`, …).
Prebuilt `.zip` packages are attached to [Releases](../../releases)
(no git needed), and GitHub Actions runs the same pre-publish checks on every push.
The methodology, criteria, report structure and Python rendering scripts are fully portable;
only the data-scraping step is tied to a specific browser-automation backend.

---

## License

[MIT](LICENSE)
