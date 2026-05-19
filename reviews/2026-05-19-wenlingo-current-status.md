# WenLingo 当前状态总结

日期： 2026-05-19



## 1. 当前一句话状态

**WenLingo 当前已经从“可演示 MVP 骨架”推进到“demo family 可独立完成一次作文 + 句子内测体验”的状态。**

它目前最成熟的部分是：

```text
家庭入口
-> 选择 / 切换 4 个 demo child profiles
-> Dashboard
-> 作文城堡：初稿 -> AI 点评 -> 单一修改任务 -> 二稿 -> 对比 -> 结算 -> 家长报告证据
-> 句子工坊：原句 -> 升级句 -> AI 反馈 -> 结算
-> 阅读峡谷等未完成模块显示友好施工中状态
```

当前不是公开发布版，也不是完整家庭账号系统。Family Test Readiness 设计明确说，本轮目标是让普通家庭可以在浏览器里独立理解、切换、验证 4 个 demo child profiles，而不是做正式账号、权限、完整阅读峡谷或复杂游戏系统。

## 2. 当前已经完成 / 通过验证的能力

### 2.1 家庭内测导航已经基本成立

当前已经具备一个 demo family 入口体验。Family Test Readiness 的 hard scope 包括全局 topbar、当前孩子显示、4 个孩子切换、Dashboard 进入作文和句子任务、阅读峡谷施工中状态、父母报告导航等。

Manual QA 结果显示：

- family entry 后不需要手动编辑 URL；
- child switcher 能切换到对应孩子 Dashboard；
- Dashboard 句子任务卡能进入句子工坊；
- 作文城堡可通过可见 top navigation 进入；
- 阅读峡谷施工中页面可以返回 Dashboard。

这说明当前已经从“开发者知道 URL 才能跑”进化到了“普通家庭测试者可以靠可见 UI 跑一遍”。

### 2.2 4 个孩子画像已经可展示、可切换、可验证

当前 4 个 seed/demo child profiles 已经通过 QA：

| 孩子 | 当前画像定位     | QA 结果 |
| ---- | ---------------- | ------- |
| 小宇 | 主线真实孩子画像 | pass    |
| 小晴 | 表达空泛型       | pass    |
| 小川 | 作文结构薄弱型   | pass    |
| 小禾 | 阅读概括薄弱型   | pass    |

QA 中每个孩子的 ability values、recommendation focus、report weak point 都有差异，并且全部通过。

这已经满足 Family Test Readiness 中“4 child profiles 在 Dashboard / recommendation / report 中可区分”的目标。

### 2.3 作文城堡主链路是当前最成熟的产品能力

V0.2 的目标本来就不是补齐所有 MVP gap，而是先把小宇画像的作文修改闭环打可信：Dashboard → 作文任务 → 初稿 → 真实 LLM 结构化点评 → 修改任务 → 二稿 → 初稿 vs 二稿对比 → 结算 → 家长报告 → AI 质量评审记录。

当前作文链路已经具备：

```text
draft
-> AI feedback
-> one bounded revision task
-> revision
-> comparison
-> settlement
-> report evidence
```

最新 Manual QA 显示，小宇 real LLM essay QA 通过：返回 1 个 bounded revision task，没有替孩子重写作文；二稿对比引用了学生真实写出的细节，例如“紧紧抓着车把，手心都出汗了”“摇摇晃晃骑过花坛”“开心得跳了起来”。

### 2.4 句子工坊已经从 bare functional page 升级为真实轻任务

Family Test Readiness 要求句子工坊不再只是裸功能页，而是成为 5-8 分钟的 child-friendly light task，并升级到与作文相同的 AI quality spine。

Manual QA 显示，小宇 real LLM sentence QA 通过：

- AI 能表扬孩子加入了时间、地点、具体对象和比喻；
- 能具体对比“很美”与“清晨公园荷叶水珠”“像小灯泡”的差异；
- 下一步建议是加一个感官细节，而不是替孩子重写。

这说明句子工坊已经基本符合 PRD 中“短平快、高频、把句子写具体”的定位。

### 2.5 AI 质量脊柱已经成为项目核心资产

V0.2 质量脊柱要求每个 AI task 走以下流程：

```text
build prompt payload
-> provider.complete_json
-> capture raw response
-> Pydantic schema validation
-> retry on invalid output / provider error
-> return valid parsed output
-> if retries exhausted, return schema-valid fallback
-> write LLMCallLog
```

并要求失败不能中断孩子流程，错误细节进入 LLM 日志用于工程复盘。

当前 AI 质量相关能力包括：

| 能力                              | 当前状态                                                     |
| --------------------------------- | ------------------------------------------------------------ |
| mock/http provider 切换           | 已作为质量脊柱要求                                           |
| FastAPI dependency injection      | 作文/句子任务应通过 provider dependency                      |
| JSON schema / Pydantic validation | 已纳入核心流程                                               |
| retry / fallback                  | 已纳入核心流程                                               |
| LLMCallLog                        | 记录 provider、model、prompt_version、raw_response、output_json、validation_ok、error_message、retry_count |
| student_id traceability           | Family readiness 要求加入                                    |
| real LLM QA                       | 小宇作文和句子均已有 QA 记录                                 |

这部分已经超过最初 PRD 中“多 LLM 后端基础版”的粗粒度要求。PRD 只要求抽象 Provider 接口；当前实现方向已经进一步覆盖了结构化输出、可观测性、fallback 和人工质量评审。

## 3. 当前与 PRD V0.1 的主要 Gap

PRD V0.1 的原始目标是一个完整学习数据飞轮：

```text
入门诊断
-> 生成初始能力画像
-> 推荐今日任务
-> 完成阅读 / 句子 / 作文训练
-> AI 反馈与游戏化结算
-> 能力值更新
-> 生成家长周报
-> 推荐下一轮任务
```

PRD 明确把学生首页、入门诊断、句子升级、作文训练、轻量阅读、游戏化结算、家长周报、多 LLM 后端列入 V0.1 必做范围。

当前 gap 可以概括为：**作文与句子主线很强，家庭 demo 可跑通；但完整学习数据飞轮尚未闭合。**

## 4. Gap 明细

### Gap 1：入门诊断还没有成为真实首次体验入口

PRD 要求首次使用流程是：

```text
家长创建账号
-> 创建孩子档案
-> 孩子进入入门诊断
-> 完成阅读小测 + 句子升级 + 小短文
-> 系统生成初始能力画像
-> 系统推荐今日任务
```

并且产品信息架构中有完整入门诊断模块：阅读小测、句子升级小测、小短文写作、初始能力画像。

当前状态更接近：

```text
demo family entry
-> 选择 4 个预置孩子画像
-> Dashboard 展示画像和推荐
```

也就是说，当前 4 个画像是可验证的 seed/demo profiles，但还不是由真实诊断流程生成的初始能力画像。

**评审重点：**

- 当前 seed profile 与未来真实 assessment 生成画像之间是否有清晰数据模型衔接？
- 是否存在硬编码推荐逻辑，未来难以替换为 assessment-driven recommendation？
- 是否需要先补一个极简 assessment，而不是完整诊断？

### Gap 2：阅读峡谷仍是施工中，读懂力数据来源不足

PRD 把阅读训练列为 V0.1 必做功能，要求轻量版阅读训练具备文章、题目和 AI 反馈。

当前 Family Test Readiness 明确把 “No complete Reading Canyon rewrite” 列为 non-goal，并要求阅读峡谷等未完成模块显示友好施工中状态。

这在当前阶段是合理取舍，但它造成一个产品层 gap：读懂力 / 阅读概括能力目前主要靠 seed profile 展示，而不是靠真实阅读训练数据驱动。

**评审重点：**

- Reading Canyon construction state 是否只是友好占位，还是已经为后续真实 reading sessions 预留路由 / 数据模型？
- 当前 Dashboard 中 reading_power 的展示是否会让用户误以为已有真实阅读训练？
- 是否需要下一阶段优先实现 Reading Canyon v0，而不是继续 polish 作文 UI？

### Gap 3：作文前半段缺口：选材追问、素材卡、提纲

PRD 和 MVP 设计都设想作文城堡支持从题目开始：输入作文题目、AI 选材追问、提纲建议、输入初稿、AI 点评、怪物识别、修改任务、二稿提交、战斗结算。

当前最成熟的是：

```text
已有初稿
-> AI 点评
-> 修改任务
-> 二稿
-> 对比
```

也就是“会修改”的后半段非常强，但“从不知道写什么到形成初稿”的前半段仍弱。

**评审重点：**

- 当前 Essay Castle 是否只适合已有初稿场景？
- 作文题目入口、选材追问、素材卡、提纲是否有代码雏形或完全缺失？
- 后续补选材追问时，是否能复用现有 AI quality spine？

### Gap 4：能力画像更新与推荐仍偏 demo 化，数据飞轮没有完全转起来

MVP 设计要求系统能根据训练数据持续更新能力画像，家长能看到孩子练了什么、哪里进步、下一步练什么。

PRD 也要求每次训练后能力值更新，再生成家长周报，并推荐下一轮任务。

当前已验证的是：

- 4 个 seed profile 能显示不同 ability shape；
- recommendation focus 能因 profile 不同而变化；
- report weak point 能因 profile 不同而变化。

但还需要确认：

- 每次作文 / 句子训练是否真实更新 ability profile？
- ability_delta 是否持久化？
- 下一轮推荐是否由训练结果动态驱动，还是主要由初始 seed profile 决定？

**评审重点：**

- 检查 ability update 是否真实存在，而不是 UI 展示层模拟。
- 检查 GameEvent / EssayVersion / SentenceTraining 是否能反向驱动 report 和 recommendation。
- 检查推荐逻辑是否集中、可测试、可解释。

### Gap 5：家长报告目前更像阶段证据报告，不是完整周报系统

PRD 中家长周报要求包含练习数据、进步点、建议。

当前家长报告已经能引用作文二稿对比证据，这一点是强项；V0.2 QA 中也验证了家长报告能引用真实修改证据。

但完整周报还缺：

- 最近 7 天训练次数；
- 阅读 / 句子 / 作文训练分布；
- 能力变化趋势；
- 最佳句子 / 最佳修改；
- 下周建议；
- 基于真实训练历史的薄弱点分析。

**评审重点：**

- report 当前读取的是实时训练记录，还是预置 profile / 最近 essay evidence？
- report 是否能优雅处理无数据、只有句子、只有作文、未来有阅读的情况？
- report schema 是否支持未来周报扩展？

### Gap 6：游戏化仍是轻量结算，不是成长系统

PRD 中游戏化包括打怪、升级、技能、徽章、地图、战斗结算，并要求游戏化必须映射真实学习行为。

当前已有：

- XP / level / settlement；
- problem monster 的雏形；
- child-friendly encouragement；
- map/module navigation 的雏形。

但尚未完整具备：

- 徽章进度；
- 长期地图关卡；
- 连续练习；
- 最佳作品收藏；
- 训练历史成长记录；
- monster progress / skill unlock。

Family Readiness 也明确把复杂 gamification、pet、map progression、badge tree 排除在本轮范围外。

**评审重点：**

- 当前游戏化是否只是 UI copy，还是有 GameEvent 持久化？
- XP / level 的规则是否稳定、可解释、可测试？
- 后续加 badge 是否会破坏现有数据模型？

### Gap 7：测试和数据库状态需要重点审

Manual QA 最终结论是 “pass with follow-up”，并特别提醒：Family-test readiness 在 fresh local QA database 中通过；复用 E2E 前需要 refresh 或 migrate stale local SQLite files，例如 `playwright-e2e.db`。

这说明当前可能存在一个工程风险：**测试通过依赖 fresh DB，旧 DB/migration 状态可能导致 E2E 不稳定。**

**评审重点：**

- Alembic / SQLModel migration 是否完整覆盖当前模型？
- stale SQLite 文件是否会误导本地 E2E 结果？
- 测试 setup 是否每次创建 fresh DB？
- 是否需要明确“不要复用旧 playwright-e2e.db”的开发协议？

## 5. 当前状态的模块评级

| 模块            | 当前状态                                                | 评级 |
| --------------- | ------------------------------------------------------- | ---- |
| 家庭入口 / 导航 | 已可用，QA pass                                         | B+   |
| 4 孩子画像      | 可切换、可区分、QA pass                                 | B+   |
| Dashboard       | 可作为任务入口，但作文入口仍有历史偏差需确认            | B    |
| 作文后半段闭环  | 当前最成熟，真实 LLM QA pass                            | A-   |
| 句子工坊        | 已升级为真实轻任务，真实 LLM QA pass                    | B+   |
| AI 质量脊柱     | 架构方向正确，具备 DI / schema / retry / fallback / log | A-   |
| 家长报告        | 能展示具体证据，但周报系统不足                          | B-   |
| 入门诊断        | 与 PRD gap 大                                           | C-   |
| 阅读峡谷        | 当前施工中                                              | D    |
| 游戏化长期成长  | 有结算雏形，缺长期系统                                  | C+   |
| 能力数据飞轮    | seed profile 可演示，真实动态闭环需审                   | C+   |
| 测试 / E2E      | 主流程 QA pass，但 stale DB 是 follow-up                | B-   |

## 6. 建议的评审目标

建议不要泛泛评“代码质量”，而是围绕下面 8 个问题做 targeted review。

### Review 1：当前 Family Test Readiness 是否真的满足设计完成定义？

对照 completion definition 检查：

- 普通测试者是否无需手动 URL？
- topbar / child switcher 是否全路径稳定？
- Dashboard 是否能进入 essay 和 sentence？
- Reading Canyon 是否友好施工中？
- backend/frontend/E2E 是否覆盖 acceptance points？
- QA 记录是否和实际代码一致？

### Review 2：AI quality spine 是否在作文和句子两条线真正复用？

重点查：

- route 是否仍有 `MockLLMProvider()` 直接实例化；
- 是否统一走 provider dependency；
- 是否统一走 validated task runner；
- retry/fallback 是否有失败测试；
- fallback 是否 schema-valid 且 child-friendly；
- LLMCallLog 是否记录 student_id、prompt_version、raw_response、validation_ok、retry_count。

V0.2 对后端测试有明确要求，包括 dependency override、invalid→valid、always invalid、provider exception、LLMCallLog 字段写入等。

### Review 3：真实 LLM QA 的结论是否已经反映到 prompt/schema？

V0.2 AI QA 曾发现真实 LLM 给了 3 个修改任务，需要调整 prompt/schema，使作文点评优先输出 1 个最小可执行 revision_task。

最新 Manual QA 显示小宇 essay feedback 已返回 1 个 bounded revision task。

需要确认：

- 是 prompt 真正修正了，还是这次刚好返回 1 个？
- schema 是否允许过多 revision tasks？
- UI 是否对 provider 返回多个 task 有 graceful handling？

### Review 4：能力画像和推荐是否只是 seed data，还是已经由训练记录驱动？

重点查：

- `AbilityProfile` 是否在 sentence / essay completion 后更新；
- `GameEvent` 是否记录 ability_delta；
- Dashboard recommendation 是否读取最新能力；
- report weak point 是否来自 profile / training evidence，而不是硬编码。

### Review 5：Report 是否能承接未来周报扩展？

重点查：

- 当前 report 数据源；
- essay comparison evidence 是否结构化保存；
- sentence evidence 是否可进入 report；
- 无数据状态是否友好；
- 未来 reading evidence 是否容易接入。

### Review 6：数据库迁移和测试数据库是否稳定？

重点查：

- `LLMCallLog.student_id` migration；
- daily limit 相关配置和默认关闭；
- stale SQLite 对 E2E 的影响；
- Playwright test DB 是否 fresh setup；
- 本地开发是否有清晰 reset/migrate 指令。

### Review 7：UI 是否只是能跑，还是符合儿童内测体验？

V0.2 要求主路径不再是裸 HTML，要有温暖、清晰、行动导向的 UI；作文页要围绕“现在该做什么”组织，不让孩子迷路；错误、等待、降级反馈不能暴露技术异常。

重点查：

- loading/error/fallback 文案；
- 主行动按钮是否明确；
- essay flow 是否有状态迷失；
- sentence workshop 是否足够 child-friendly；
- parent report 是否专业但不焦虑。

### Review 8：下一阶段补 PRD gap 的代码可扩展性

重点查：

- 入门诊断是否容易接入；
- Reading Canyon v0 是否能复用现有 LLM task runner；
- 作文选材追问 / 素材卡 / 提纲是否能复用 Essay 数据模型；
- badge / training history 是否能基于 GameEvent 扩展；
- recommendation 是否能从 rule-based seed 过渡到 training-data driven。

## 7. 建议给 gstack 的评审提示词

可以把下面这段直接交给 Claude Code + gstack：

```text
请基于当前代码库和以下项目状态，对 WenLingo 做一次 targeted architecture + product-readiness review。

我的人工review当前状态文档在 ./reviews/2026-05-19-wenlingo-current-status.md

当前产品状态：
WenLingo 已从 V0.2 作文质量脊柱推进到 Family Test Readiness。目标是让 demo family 的 4 个孩子画像可以在浏览器中被普通家庭测试者理解、切换和验证。当前重点链路是：family entry -> child switcher -> Dashboard -> Essay Castle -> Sentence Workshop -> Parent Report -> Reading Canyon construction state。

请重点评审：
1. Family Test Readiness completion definition 是否真实满足，而不是只在 happy path 上满足。
2. Essay 和 Sentence 是否都真正复用了 AI quality spine：provider DI、schema validation、retry、fallback、LLMCallLog、student_id traceability。
3. 是否仍存在 route 直接实例化 MockLLMProvider、硬编码 seed profile、硬编码 recommendation/report 的问题。
4. Manual QA 中 pass 的结论是否有自动化测试支撑，尤其是 E2E、fallback、daily limit、LLM logging。
5. 当前 ability profile / recommendation / report 是否由真实训练记录驱动，还是主要由 seed data 驱动。
6. 数据库 migration 和本地测试 DB 是否稳定，特别是 stale SQLite / playwright-e2e.db 的风险。
7. UI 是否满足儿童内测体验：主路径不裸、行动按钮清晰、loading/error/fallback 文案友好。
8. 从当前代码出发，补 PRD gap 的扩展性如何：入门诊断、Reading Canyon v0、作文选材追问/素材卡/提纲、周报、长期游戏化。

请输出：
- Critical blockers
- High priority issues
- Medium priority improvements
- PRD gap risks
- Suggested next implementation sequence
- Files/modules most likely needing refactor
- Tests that should be added before next feature work
```

## 8. 最后结论

当前项目：

> **WenLingo 已经完成了一个以作文修改和句子升级为核心的 Family Test Readiness 版本。它具备 demo family 导航、4 个孩子画像、作文/句子真实 LLM QA、AI quality spine、结算与报告证据。它距离最初 PRD 的完整学习数据飞轮仍有明显 gap，主要集中在入门诊断、阅读训练、动态能力更新、周报系统和长期游戏化。**