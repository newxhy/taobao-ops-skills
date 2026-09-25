---
name: skill-frontmatter-safeedit
version: 1.4.2
display_name: SKILL.md 安全编辑与上传前校验
display_name_en: SKILL.md Safe Edit and Pre-upload Validation
description: |
  编辑 SKILL.md 的 frontmatter（name / version / description / display_name 等）时的
  **安全流程与踩坑清单**，附零依赖的**校验器 / 打包器 / 敏感信息扫描器**。
  当需要批量改技能元数据、升版本号、改名、**公开发布（开放平台 / 公开仓库）前自检**时使用。
  ★ 核心是五个实测坑：① **CRLF 文件的游离 `\r`** 破坏 YAML
  （症状：`yaml.safe_load` 报 `could not find expected ':'`）；
  ② **单行 plain scalar 里的半角 `: `** 被当成 mapping
  （症状：报 `mapping values are not allowed here`；中文全角 `：` 安全）；
  ③ **官方校验器查得比平台少** —— `quick_validate.py` 只查 `name` / `description`，
  平台却另要 `version` / `display_name` / `description_zh` / `description_en`，
  所以它永远报 `Skill is valid!`，平台却在上传第 1 步报「解析失败」；
  ④ **描述字段有长度上限** —— 实测「Skill 英文描述: 当前 1330 字符, 上限 1000 字符」，
  `description_en` 上限 1000，超长即拒；
  ⑤ **打包是二次污染点** —— 源目录验过 ≠ 包内干净，实测 zip 内仍有 1357 个裸 CR。
  **上传前的准绳：`--upload` 模式 + `pack_and_verify.py` 打包后解包复验。**
  三条纪律：**改内容必须同步升 version**、
  **6 个必填字段一个都不能少且不能超长**、
  **公开发布前必扫敏感信息**（店铺名 / 品牌名 / 合作方名 / 内部称呼 / 密钥，
  跑 `scan_sensitive.py`，词表在 `~/.workbuddy/sensitive-words.txt`）。
  校验器还查 name 合规、目录名一致、正文版本标记对账。
description_zh: 编辑 SKILL.md frontmatter 的安全流程与发布前自检，覆盖传开放平台或公开仓库前的完整检查链。五个实测坑：CRLF 游离回车破坏 YAML；单行标量里的半角冒号空格被当成 mapping；必填字段缺失；描述字段超长（实测英文描述上限 1000 字符）；打包环节二次污染，源目录验过但 zip 内仍有裸 CR。并指出官方 quick_validate.py 只查 name/description 两条，报 valid 却仍被平台拒收。平台硬性要 6 个字段，缺任一即报解析失败，超长同样被拒。三条纪律：改内容必升 version、6 字段不能少不能超长、公开发布前必扫敏感信息（店铺名、品牌名、合作方名、内部称呼、密钥）。附三个零依赖脚本：校验器 check_frontmatter.py、打包器 pack_and_verify.py（打包前 LF 化 + 打包后解包复验）、敏感信息扫描器 scan_sensitive.py。
description_en: Safe editing workflow and pre-upload validation for SKILL.md frontmatter, covering the checklist before public release. Covers five real pitfalls, stray carriage returns from CRLF breaking YAML, a half-width colon plus space in a one-line scalar parsed as a mapping, missing required fields, description fields exceeding the 1000-character cap for the English description, and packaging as a second contamination point where a clean source can still yield a zip with raw carriage returns. Also notes the official quick_validate.py checks only name and description while the platform hard-requires six fields. Three rules, bump version with any content change, keep the six fields complete and within limits, and always scan for sensitive info such as shop names, brand names and internal nicknames before publishing. Ships three scripts, a validator, a packer normalizing to LF with byte re-verification, and a sensitive-info scanner.
license: MIT
compatibility: Requires Python 3.9+. Pure standard library, no third-party dependencies and no network access.
agent_created: true
---

# SKILL.md 安全编辑与上传前校验

> **为什么需要这个技能**：给技能改元数据（改名 / 升版本 / 补 description）看着是小事，
> 但**改坏了不会立刻报错** —— 文件照样存在、内容看着完整，**直到打包上传被平台拒收、
> 或者 YAML 在某处静默解析成别的结构**。
> 本技能把"改 → 验"固化成两步，杜绝这类返工。

## 0. 最短路径

```bash
# 1) 改完先验源目录（支持传目录或 SKILL.md 文件，可多个）
python scripts/check_frontmatter.py --upload <技能目录> [<技能目录2> ...]

# 2) ⚠️ 只要打算公开发布（开放平台 / 公开仓库）→ 先扫敏感信息
python scripts/scan_sensitive.py <技能目录> [<技能目录2> ...]

# 3) 打包（内含"打包前强制 LF 化 + 打包后解包复验"，一步到位）
python scripts/pack_and_verify.py <技能目录> [输出zip]
```

三步都输出 `✅` 才去上传 / push。
**第 2 步只在自己用、不发布时可以跳过；一旦要公开，绝不能跳。**

**退出码**：校验器与扫描器都是 `0 = 通过 / 1 = 有问题` ——
可直接当 **CI 门禁**用（本仓库的 GitHub Actions 就是这么挂的）。


## 1. 五个实测踩到的坑（前两个让 YAML 静默失效，后三个让平台静默拒收）

### 坑 ① CRLF 文件的游离 `\r`（2026-09-20 实测）

**症状**：`yaml.safe_load` 报 `could not find expected ':'`，
错误位置指向一个**看起来正常的中文句子**，例如：

```
line 35, column 1:
    。v1.3 起把「发现变化 → 引导找到原因」提为总纲 ...
    ^
```

**为什么会这样**：Windows 上的 SKILL.md 通常是 **CRLF** 换行。用

```python
i = s.find('\n')          # ← 只找到 \n，\r 留在前面
val = s[j:i]              # ← val 末尾带着 \r
val = val.rstrip('。')     # ← 末尾其实是 \r，rstrip 完全没生效
s = s[:j] + val + '。新句子' + s[i:]   # ← \r 把句子劈成两行
```

拼接后 `\r` 夹在句中（YAML 规范把 `\r` 也当行分隔符），
**后半句跑到行首、无缩进 → 被当成一个新的 key → 语法错误。**

**对策（三条，至少用一条）**：

| 做法 | 写法 |
|---|---|
| 读文件时不转换换行 | `io.open(p, 'r', encoding='utf-8', newline='')` |
| 定位行尾用 CRLF | `i = s.find('\r\n')` |
| 用「整行匹配」代替「找 `\n` 再切片」 | `re.sub(r'^description_zh:.*$', new, s, flags=re.M)` |
| 修完必查裸 CR | `re.findall(r'\r(?!\n)', s)` 必须为空 |

> **收尾必做**：`re.sub(r'\r(?!\n)', '', s)` 清除游离 `\r`，
> 然后重新 `yaml.safe_load` 确认。

### 坑 ② 单行 plain scalar 里的半角 `: `

**症状**：`mapping values are not allowed here`，错误位置指向英文句子里的冒号：

```
... m deep dive. Its core principle: a report must turn every change ...
                                       ^
```

**原因**：`description_zh` / `description_en` 这类**单行 plain scalar**，
**值里出现半角冒号+空格（`: `）就会被 YAML 解析成 `key: value` 映射**，直接报错。

**对策**：

- **中文全角 `：` 是安全的**，可放心用。
- 英文句子避免 `: `，改写成 `is that` / `—` / 直接去掉冒号。
- 若确实需要，把该字段改成**块标量**（`description_zh: |` + 两空格缩进）或加引号。
- ⚠️ **`description: |` 块标量内部不受此限** —— 块标量里 `: ` 安全。
  **只有单行 plain scalar 要小心。**

### 坑 ③ 官方校验器查得比平台少（2026-09-20 实测，最隐蔽）

**症状**：本地全部检查通过 —— `package_skill.py` 报 `Skill is valid!`、
`quick_validate.py` 报 `Skill is valid!`、YAML 也能解析 —— **传到平台上却报「解析失败」**。

**真因**：翻 `quick_validate.py` 源码，它对 frontmatter **只查两条**：

```python
if 'name:' not in frontmatter:        return False, "Missing 'name' in frontmatter"
if 'description:' not in frontmatter: return False, "Missing 'description' in frontmatter"
```

而平台实际要 `name` / `version` / `display_name` / `description` / `description_zh` / `description_en`。
**中间那四个字段官方校验器一个都不查**，所以它永远报 valid。

```bash
# 反例（本机实测，报 valid 但上传被拒）
python "$SC/scripts/quick_validate.py" <技能目录>     # → Skill is valid!   ❌ 不可信
```

**修法**：**上传前必须跑本脚本的 `--upload` 模式**，它是按平台实际要求查的：

```bash
python scripts/check_frontmatter.py --upload <技能目录>   # 缺字段会报「平台会拒收」
```

> ⭐ **结论**：官方校验器 + 打包器 = **只保证"格式像技能"，不保证"能上传"**。
> **上传前唯一的准绳是本脚本的 `--upload`。**

### 坑 ④ 描述字段有长度上限（2026-09-20 实测，英文描述 1000 字符）

**症状**：字段齐全、YAML 正常、本地所有检查都过 —— **平台仍报「解析失败」**：

```
解析失败：
Skill 英文描述: 当前 1330 字符, 上限 1000 字符
```

**真因**：平台对描述类字段**另有长度上限**，而**官方校验器与打包器都不检查长度**
（`quick_validate.py` 只看字段名在不在，`package_skill.py` 更是什么都不看）。

| 字段 | 平台上限 | 实测依据 |
|---|---|---|
| **`description_en`** | **1000 字符** | ✅ 平台报错原文（2026-09-20 两次上传实测）|
| `description_zh` | 未实测 | ⚠️ 保守压在 **≤ 400** |
| `description` | 未实测 | ⚠️ 保守压在 **≤ 1000**（已过审的版本实测 972）|
| `display_name` / `display_name_en` | 未实测 | 很短，基本不触线 |

> ⭐ **写法建议（留 5% 余量）**：`description_en` 目标 **≤ 950**、`description_zh` ≤ 400、
> `description` ≤ 1000。
> **超了先砍"细节枚举"**（15 个板块的完整清单可压成「十五个板块包括…」），
> **必须保住"触发词 + 第一性原理"** —— 决定召回的就是这两样。
>
> ⛔ **反面教材**：本技能文档上一版曾写「长度量级 zh 约 370 / en 约 1,100 字符」，
> **把超限的写法当成了参照值** → 直接导致 `taobao-item-ops-report` 首次上传被拒。
> **参照值只能从"已通过审核的版本"里量**，且必须核对是否 ≤ 平台上限。

**校验器已内置这条检查**（`--upload` 模式下 `description_en` 超限判 ✗，其余超限告警）。

### 坑 ⑤ 打包是二次污染点：**包内字节 ≠ 源目录**（2026-09-20 实测，最容易被漏）

**症状**：源目录已经 `check_frontmatter.py --upload` **全绿**，
**上传后平台仍报「解析失败」**。

**真因**：校验器看的是**源目录**，平台收的是 **zip 包里的字节** —— 这是两份东西。
实测 `sycm-ops-daily-report` v1.3：源目录明明已修干净，
**zip 内的 SKILL.md 仍有 1357 个裸 CR**（整份文件是 CRLF）。

**为什么会复发**：**在 Windows 上只要用编辑器 / IDE / 脚本写过一次 SKILL.md，
行尾符就可能被静默写回 CRLF** —— 上一版修过，不代表这一版没被写回。
（这正是「上一版能过不代表这一版能过」的第二重含义：不只内容会变，**字节也会变**。）

**对策**：把「校验 → 打包 → 复验」串成一条链，用 `scripts/pack_and_verify.py` 一步做完：

```bash
python scripts/pack_and_verify.py <技能目录> [输出zip] [--root 包内根名]
# 不带输出路径时默认写到 <技能目录>/../dist/<技能名>.zip
```

它会依次做三件事：

1. **打包前**对源目录**全量 LF 化**（`.md/.html/.sh/.py/.json/.css/.js`，保留 BOM 状态）
2. 打包（固定时间戳 → 内容哈希稳定，便于比对两次打包是否一致）
3. **打包后解包复验包内字节**：裸 CR / BOM / 非 UTF-8 / 6 字段齐全 / 长度上限 /
   zip 完整性 / 目录名与 `name` 一致

输出 `✅ 可以上传` 才算过；退出码 0 / 1 可直接串进脚本。

> ⭐ **一句话**：**打包后必须再验一次，验的是包里的字节，不是源目录。**
> 「源目录校验通过」**不等于**「包是干净的」。

## 2. 三条纪律

### 纪律 ① 改内容必须同步升 `version`

**症状**：文档正文里出现 `v1.3` 这类版本标记（如某节标题写着「（`v1.3` 打通）」），
但 frontmatter 还是 `version: 1.2.0`。

**为什么危险**：平台审核按 `version` 判断版本，**审核通过的版本号与实际内容不符**，
后续排查"这个功能是哪个版本加的"会全错。

**对策**：改完内容后对账 ——

```python
marks = set(re.findall(r'v(\d+\.\d+)', body))     # 正文里的版本标记
assert not [x for x in marks if x > version]      # 不许有比 frontmatter 更新的标记
```

校验器已内置这条检查。

> ⚠️ **校验器的一个已知误报点**：文档里**举例提到**的版本号（如 `` `v1.3` ``）
> 不是本技能的版本标记。校验器已**剔除代码块与行内代码**后再扫描 ——
> **所以写文档时把"举例的版本号"放进反引号里**，即可自动豁免。

### 纪律 ② 必填字段一个都不能少

**实测**：先后两次因 frontmatter 缺字段被开放平台**在上传第 1 步「配置技能」直接拒收**。

平台拒收时的原话（照抄，用于自查时对号入座）：

```
解析失败：
缺少 Skill 中文描述（description_zh），请在 SKILL.md frontmatter 中填写
缺少 Skill 英文描述（description_en），请在 SKILL.md frontmatter 中填写
```

| 字段 | 说明 | 平台要求 | 长度上限 |
|---|---|---|---|
| `name` | 小写字母/数字/连字符，**必须与目录名一致** | **必填** | — |
| `version` | `X.Y.Z` | **必填** | — |
| `display_name` | 中文可读名（给人看） | **必填** | 短，不触线 |
| `description` | 召回的关键（**触发词写全**，技能名基本不参与召回） | **必填** | 保守 ≤ 1000 |
| `display_name_en` | 英文可读名 | 建议 | 短，不触线 |
| **`description_zh`** | **中文描述，单行 plain scalar** | **必填**（缺 → 「解析失败」）| 保守 ≤ 400 |
| **`description_en`** | **英文描述，单行 plain scalar** | **必填**（缺 → 「解析失败」）| **实测 1000**（超 → 「解析失败」）|
| `agent_created` | 自建技能标 `true` | 自建时标 | — |

> 🔴 **两个多语言描述字段是硬门槛，不是"建议"** —— 2026-09-20 实测：
> 只写了 `description`、字段齐全度看着"很标准"，**平台照样拒收**。
> **写法照抄已通过审核的同类技能**（本机参照 `sycm-ops-daily-report`）：
> **单行 plain scalar**、值内**不含半角 `: `**、**长度在平台上限内**
> （`description_en` ≤ 1000，实测；详见坑 ④）。
> ⛔ **别再照抄"en 约 1,100 字符"这种量级** —— 那是超限值，会直接被拒。

> ⚠️ **`agent_created: true` 是权限边界**：只有自己创建的技能才可被修改。
> **别人写的技能（无此字段）不要改**，即使内容有误 —— 应提示用户或另建新技能。

### 纪律 ③ 公开发布前必扫敏感信息（2026-09-20 实测踩到）

**症状**：技能**功能完全正常、格式全部合规、平台审核照样能过** ——
但正文里躺着**你的店铺名、合作方的店名、你和 AI 之间的内部称呼**。
传开放平台 → 所有下载者可见；推公开仓库 → **全世界可见，且永久留在 git 历史里**。

**真因**：技能是"实战里长出来的"，写案例时会顺手把真实店名写进去。
**这类问题不报错、不崩、不影响功能**，所以自己根本发现不了 ——
直到有人问你"这家店是你的？"

**实测（2026-09-20）**：某店铺日报技能在公开发布前扫描，查出来：

- **自有店铺名 × 6** —— 作为"实测案例"写在正文里
- **合作方店铺名 × 5** —— 把人家"单品转化下降 = 断色"的**经营问题**当成案例写了
- **内部称呼 × 15** —— 内部昵称 + 「原话：…」这种引用，对外人完全莫名其妙，
  还等于告诉所有人"这是一份内部对话记录"

**风险分档，不是一回事**：

| 类型 | 风险 | 说明 |
|---|---|---|
| **密钥 / Token / 邮箱 / 手机号** | 🔴 最高 | 会被直接滥用 |
| **合作方 / 别人的店** | 🔴 最高 | 暴露别人的经营问题 = **商业关系风险**，不只是隐私 |
| **自己的店 / 品牌** | 🟡 中 | 别人能摸到你的店 → 看你的打法、抄你的词 |
| **内部称呼 / 个人标识** | 🟡 中 | 对外人无意义，还暴露内部对话痕迹 |

**对策**：`scripts/scan_sensitive.py` + 一份词表。

```bash
python scripts/scan_sensitive.py --init-words    # 一次性：生成词表模板
python scripts/scan_sensitive.py <技能目录>      # 以后每次发布前跑
```

词表固定放 `~/.workbuddy/sensitive-words.txt`（**存在即自动加载**，不用每次敲参数），
把你的**店铺名 / 品牌名 / 合作方名 / 内部称呼**逐行写进去。

扫描器查两类东西：

- **通用模式**（无需配置）：邮箱、手机号、密钥 / Token、本机绝对路径、≥8 位长数字
- **词表命中**：你自己的那份清单

结果分 `🔴 高危 / 🟡 待确认 / ⚪ 提示` 三档，并**自动降噪** ——
`800000000000` 判为示例 ID、`20xxxxxx` 判为日期、含 `<占位符>` 的路径直接跳过。
退出码 1 表示有高危，可直接串进发布脚本。

> ⭐ **脱敏手法：案例全留，只换主体名。**
> 「`某工业品店实测：08-24~08-31 完全无券 8 天`」和「`A 店实测：…`」**说服力完全一样** ——
> 读者要的是"有真实案例"，不是"案例里的店叫什么"。引内部原话改成「**实战经验**：」+ 叙述句。
>
> ⛔ **公开仓库是"一次泄漏、永久留存"**：`git rm` 掉文件**不算**，内容还在历史 commit 里。
> 所以**必须在第一次 push 之前**扫干净 —— 那是唯一成本最低的时间点。

## 3. 安全编辑的标准流程

1. **备份**：把 SKILL.md 复制成 `SKILL.md.<原因>_bak`（例如 `SKILL.md.presanitize_bak`）
   ⚠️ **最好移到技能目录外**（如 `<工作区>/_skill_backups/`）。
   打包器现在会跳过疑似备份文件（`_bak` / `.bak` / `_backup` / `.orig` / `.old` / `~`），
   但把备份留在技能目录里终究是隐患 —— 换别的工具打包就漏进去了。
2. **读原文**：`newline=''` 读，**先 dump repr 看清真实字节**，不要凭显示猜
3. **替换**：优先用锚点整段替换，**不要并行多次 Edit 同一文件**（会互相覆盖）
4. **清游离 CR**：`re.sub(r'\r(?!\n)', '', s)`
5. **写回**：`newline=''` 写，**不要做换行符转换**
6. **校验**：`python scripts/check_frontmatter.py --upload <目录>` + 内容关键词断言
7. **⚠️ 扫敏感信息**：`python scripts/scan_sensitive.py <目录>`
   **自己用可跳；只要打算公开发布（开放平台 / 公开仓库）绝不能跳** —— 见纪律 ③
8. **打包**：`python scripts/pack_and_verify.py <技能目录> <输出zip>`
   （自带"打包前 LF 化 + 备份排除"，见坑 ⑤）
9. **验包**：打包器已内置 —— 它重新解 zip、**对包内字节**复跑 CR / 编码 / 6 字段 / 长度检查
   （⚠️ 不要跳过；源目录干净 ≠ 包干净）

## 4. 排障速查

| 报错 | 真因 | 修法 |
|---|---|---|
| `could not find expected ':'` | 游离 `\r` 把句子劈成两行 | 见坑 ①，清裸 CR |
| `mapping values are not allowed here` | 单行 scalar 里有 `: ` | 见坑 ②，改写或改块标量 |
| 平台报「解析失败：缺少 Skill 中文描述（description_zh）/ 英文描述（description_en）」 | **缺上传必填字段** | 见坑 ③，补两个多语言描述 |
| 平台报「解析失败：**Skill 英文描述: 当前 N 字符, 上限 1000 字符**」 | **字段超长** | 见坑 ④，压缩到上限内（en 目标 ≤ 950）|
| 其他平台拒收（无明确报错） | 缺必填字段 | 补齐 `name`/`version`/`display_name`/`description`/`description_zh`/`description_en` |
| **源目录校验全绿、上传仍报「解析失败」** | **包内字节 ≠ 源目录**（打包环节被写回 CRLF）| **见坑 ⑤**，改用 `pack_and_verify.py`，务必验**包内**字节 |
| **发布后有人问"这家店是你的？"** | **正文带着真实店铺名 / 合作方名 / 内部称呼** | **见纪律 ③**，跑 `scan_sensitive.py` 脱敏后重发（公开仓库还需清 git 历史）|
| 包里出现 `xxx_bak` 备份文件 | 备份留在技能目录里了 | 移到技能目录外；打包器会跳过疑似备份并打印提示 |
| `Skill is valid!` 但 YAML 报错 | **打包器校验 ≠ YAML 校验** | 两者都要过，别只信打包器 |
| `Skill is valid!` 但平台上不去 | **官方校验器只查 `name`/`description` 两条** | 见坑 ③，必须跑本脚本 `--upload` |
| 目录名与 `name` 不一致 | 改名时漏改目录 | `mv` 目录，并重打包 |
| 正文标了更高版本、frontmatter 未升 | 改了内容忘升 `version` | 若是**本技能自己的**版本标记 → 升 `version`；若是**引用外部规范**的版本号 → 忽略（或放进反引号让校验器豁免） |
| **改了好几处，文件里只生效一部分**（且工具回执全是"成功"）| **一次消息里对同一文件并行发多个 Edit，互相覆盖并静默丢改动**。**实测两次**：2026-09-22（4 处只落地 3 处）；**2026-09-23（3 处只落地 2 处，导致自检器测试出现「提示词写着 whitening 却判 ✅ 通过」的假绿——差点据此下错结论）** | **改用 `python scripts/safe_multi_edit.py <文件> <edits.json>`**：先对全部替换逐个断言命中次数，**任一处不达标就整批不写盘**，写盘后回读校验（新串在、旧串消失）。**不要并行 Edit 同一文件，也不要只信工具回执** |
| 替换后行为没变，但代码看着是新的 | 上面那条的**衍生症状**：部分改动落地 → 新旧逻辑混在一个文件里，比全失败更难查 | 修完**必须回读文件确认**（`grep` 关键词计数），或直接用 `safe_multi_edit.py` 的回读校验 |
| `safe_multi_edit.py` 报「**旧串仍在**」但改动其实生效了 | **追加型替换**（new 以 old 开头，如"在段末补一段"）触发校验**假阳性**——替换后旧串当然还在 | **2026-09-23 已修**（仅当 `old not in new` 时才查旧串）。旧版脚本遇到这种情况会 `exit 1`，**别据此回滚**；先 `grep` 确认实际内容 |
| 自检/校验脚本报失败，但人看是对的 | **判据本身有缺陷**（不只是被检对象的问题） | 2026-09-23 一天内撞到三次：① 自检器把 `at 0.00 seconds` 固定句式当数字泄漏；② 品类检查把硬违规和边界词放同一档，出现"写着 whitening 却判 ✅ 通过"；③ 本次的旧串假阳性。**凡判据报错，先验判据** |

> ⭐ **最重要的一条**：`package_skill.py` 报 `Skill is valid!` **不代表能上传成功**
> —— 2026-09-20 实测两件事同时发生：打包器报 valid，`yaml.safe_load` 失败；
> 打包器又报 valid，平台却报「解析失败」。
> 原因是**官方 `quick_validate.py` 只检查 `name` 和 `description` 两个字段**（源码实测），
> 平台要的 `version` / `display_name` / `description_zh` / `description_en` **一个都不查**。
> **所以上传前必须跑本脚本的 `--upload` 模式，不能拿打包器的输出当准绳。**
>
> 同样地，**"上一版能过"也不代表"这一版能过"** —— 2026-09-20 的两次拒收分别是
> **"字段缺失"** 与 **"字段超长"**，都是**内容改动引入的**，与格式对不对无关。
> **但凡动过 frontmatter，就必须重跑 `--upload`。**
>
> 第三重：**"源目录干净"也不代表"包干净"** —— 见坑 ⑤。
> 2026-09-20 实测 `sycm-ops-daily-report` v1.3：源目录 `--upload` 全绿，
> **zip 内却藏着 1357 个裸 CR**。Windows 上每次写文件都可能把 CRLF 带回来。
> **所以"验源目录"与"验包内字节"是两件事，必须都做**（`pack_and_verify.py` 一次做完）。


---

## 5. 官方标准字段 vs 平台扩展字段（2026-09-20 查证 [agentskills.io/specification](https://agentskills.io/specification)）

`SKILL.md` 是**开放标准**（Anthropic 发起，70+ 工具采纳）。
WorkBuddy 用的是「**开放标准 + 自家扩展**」，所以跨工具发布
（GitHub / Claude Code / Codex CLI / Cursor）前必须分清哪些字段是谁的：

| 字段 | 归属 | 换到别的工具 |
|---|---|---|
| `name` / `description` | ✅ 官方标准 | **照读**，召回能力不丢 |
| `license` / `compatibility` / `metadata` / `allowed-tools` | ✅ 官方标准（可选） | 照读 |
| `version` / `display_name` / `description_zh` / `description_en` | ⚠️ **WorkBuddy 扩展** | **静默忽略**（不报错，也不生效）|

### Codex 端实测（2026-09-25，实测环境：Codex 桌面版 26.917 + 本机 skills 目录）

把本仓库三个技能原样放进 `~/.codex/skills/` 后，用 **`codex debug prompt-input`**
（把「模型实际看到的内容」原样吐出来，**不调模型、不花钱**）逐条核对，结论：

| 观察项 | 结果 |
|---|---|
| 技能是否被识别 | ✅ 三个全部出现在模型可见的技能清单里 |
| 多行块标量 `description: \|` | ✅ 解析正确，整段落进清单（含中文与换行）|
| WorkBuddy 扩展字段（`version` / `display_name` / `description_zh` / `description_en` / `platform` / `agent_created`）| ✅ **静默忽略**，不报错、不影响加载（与上表一致）|
| `description` 长度 | ✅ Codex 端**未见**长度拒收或截断（本仓库最长的主描述超过 1000 字符仍正常）|
| 正文里的平台专属工具名 | ⚠️ 需要处理：`present_files` / `Read` / `run_in_background` 在 Codex 端没有同名工具，正文里要给出等价说法 |

**两条可复用的结论**：

1. **同一份 `SKILL.md` 可以同时发 WorkBuddy 与 Codex，不需要双份 frontmatter。**
   要改的只是正文里的平台专属**工具名**与**路径约定**，frontmatter 一个字都不用动。
2. **验证「技能有没有被工具认出来」，别靠肉眼猜**：WorkBuddy 看技能列表，
   Codex 直接跑 `codex debug prompt-input` —— 它输出的是模型真实收到的提示，
   **技能没进清单就是没生效**，比看日志可靠。

> ⚠️ 但要注意：**技能被加载 ≠ 技能依赖的工具可用**。
> 实测 Codex 端 `imagegen` 技能在清单里，但它依赖的内置 `image_gen` 工具在当前
> 模型/供应商下并不存在；同理 `view_image` 会直接返回
> `not allowed because you do not support image inputs`。
> **发布前要按「技能依赖的工具在目标端存不存在」再核一遍**，这一步不在 frontmatter 里。

**跨端自检方法**（与 frontmatter 无关，但同属"发布前必查"）：

```bash
CODEX_HOME=<一个临时目录> codex debug prompt-input "测试"   # 看技能清单里有没有你的技能
```

### 官方字段的硬约束（照抄规范，别凭记忆）

| 字段 | 约束 |
|---|---|
| `name` | ≤64 字符；小写字母 / 数字 / 连字符；**不得连续连字符**；**必须与父目录名一致** |
| `description` | ≤ **1024** 字符（WorkBuddy 实测更严：**1000** —— **取更严的**）|
| `compatibility` | ≤ **500** 字符 |
| `license` | 许可证名，或引用随包附带的许可证文件名（本仓库统一 `MIT`）|

### 版本号放哪：一个必须做的取舍

官方建议把版本放 `metadata.version`（`metadata` 是 string→string 映射），
WorkBuddy 则要**顶层 `version`**。两者冲突。

> ⛔ **本项目的取舍：只用顶层 `version`，不加 `metadata.version`。**
>
> **理由**：平台对描述字段的要求是「单行 plain scalar」——这说明它的解析器
> **可能是逐行 key 提取，而不是完整 YAML 解析**。若如此，嵌套的 `  version:` 缩进行
> 会被误当顶层字段，与 `version` 撞车 → **直接「解析失败」**。
> 而收益极小（各工具实际只读 `name` / `description` 做召回）。
> **不为"正宗"去冒上传被拒的险** —— 已经被拒两次了，教训够贵。

### 已采纳的官方字段

三个技能均已加 `license: MIT` 与 `compatibility`（扁平单行 scalar，零嵌套）。
校验器 `check_frontmatter.py` 会对 `compatibility` 做 ≤500 长度告警
（**不影响 WorkBuddy 上传，故只告警不判 fail**）。

## 6. 从外部来源安装技能（2026-09-23 实战：三个 H3 技能）

前面五节管的是「**改**已有的技能」和「**传**技能」。这一节管前面那一步：**把外部来的技能装进技能库**。

### 6.1 先分类：这个技能能不能改？

| 来源类型 | 判别特征 | 能不能改 | 处置 |
|---|---|---|---|
| 第三方整合包 | 有 README、作者自述、版本号 | ✅ 可**追加**注释（不改原文） | 原文保留 + 顶部加本机说明 |
| **官方快照** | 目录里有 `SOURCE.md` / 哈希清单 / 「Do not edit ... in place」 | ❌ **一个字节都不能动** | 保真复制 + **旁挂** `WORKBUDDY-NOTES.md` |
| 技能市场 / 公开仓库 | 从市场或 GitHub 装 | 通常原样 | 原样复制 |

> 判别只看一条：**目录里有没有哈希校验声明。** 有 → 当只读快照处理，任何改动都会让校验永久失效。

### 6.2 保真安装法（四步，一步都不能省）

1. **用 `shutil.copytree` 复制**，不要手工拖拽（拖拽会漏隐藏文件）
2. **立刻对哈希**：从 `SOURCE.md` 里解析期望值，逐个 `sha256` 对照
3. **旁挂 `WORKBUDDY-NOTES.md`** 写本机信息（来源、上游 commit、配套关系、校验命令）——**不要就地改快照文件**
4. **装完再核一次**哈希，确认没被后续操作污染

```python
import hashlib, os, re
def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(65536), b''): h.update(c)
    return h.hexdigest()
# SOURCE.md 里的形式：- `references/x.txt`: `<64位hex>`
want = dict(re.findall(r"`([^`]+)`:\s*`([0-9a-f]{64})`", open(src, encoding="utf-8").read()))
for rel, exp in want.items():
    print(("OK  " if sha256(os.path.join(dst, rel)) == exp else "BAD "), rel)
```

### 6.3 可改型技能的加法（不破坏可追溯性）

- **正文逐字不动**，只在 frontmatter 之后**追加**一段带日期的说明
- 追加内容写四件事：**来源路径**、**触发词**、**上游哪些字样在本机无效**（例如 frontmatter 写着 `Use when Codex needs to...`——保留原文但指出不影响本机触发）、**下游配套技能**
- 明确标注改了哪里：`（正文与上游逐字一致，未改动）`

### 6.4 安装后验证（三件，缺一件都可能白装）

| # | 验什么 | 怎么验 |
|---|---|---|
| 1 | **结构完整性** | 遍历列全部文件 + 体积，与源目录对账 |
| 2 | **frontmatter 合规** | 跑本目录 `scripts/check_frontmatter.py` |
| 3 | **系统是否真的入册** | 跑 `workbuddy-skill-manager` 体检，`total_skills` 应 +N，且新技能名出现在 `installed` 列表 |

> **Codex 端对应做法**：`codex debug prompt-input "测试"` —— 它输出模型真实收到的提示，
> 在里面搜技能名即可；**技能没进清单就是没生效**（比看日志可靠）。详见 §5 的「Codex 端实测」。

> ⚠️ **坑（本机踩过）**：体检报告输出目录里若已存在 `_data.json`，那是**上一次手工导出的残留**，
> 脚本重跑**不会更新它** —— 直接读它会拿到旧数据，得出「整理没生效」的错误结论。
> **必须从新生成的 HTML 里重新提取内嵌 `DATA` 对象**，或对比 `invocable_count` / `active_7d` 这类会变的字段。

### 6.5 一个反直觉点：`assets/` 目录名不必改

WorkBuddy 官方推荐的子目录是 `references/` / `scripts/` / `templates/`，**列表里没有 `assets/`**。
但**本地技能完全不受影响** —— 技能加载只要求 `SKILL.md` 存在，其余文件由 Agent 按 SKILL.md 里的**相对路径**用 Read 工具读取，目录叫什么名字都能读到。

⇒ **第三方包里的 `assets/` 不要为了"规范"而改名**（改了会破坏与上游的一致性，还可能漏改 SKILL.md 里的引用路径）。**只有打算上架时**才需要对齐官方子目录规范。
