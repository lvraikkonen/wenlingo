# WenLingo MVP Gstack 综合评审

日期：2026-05-15
评审范围：MVP (specs/2026-05-06-mvp-design) + V0.2 Quality Spine (specs/2026-05-14-v0.2-quality-spine-design)
评审依据：ai_chinese_literacy_prd_v_0_1.md, CLAUDE.md, docs/ai-collaboration-protocol.md
评审人：Claude Code + gstack

---

## 1. CEO / Product Strategy Review

### 1.1 北极星一致性

产品从 V0.1 的"验证学习数据飞轮"到 V0.2 的"让真实孩子完成可信作文修改内测"，方向收敛清晰。PRD 对标的 Renaissance Learning 思路在 MVP 设计中得到了忠实体现：能力画像、个性化推荐、成长报告三大支柱都已落地。

**通过。**

### 1.2 V0.2 范围纪律：深度优先的刻意决策

V0.2 质量脊柱 spec 做了一个刻意的产品决策：**将所有资源集中到"小宇画像一条作文修改链路"上，而不是把 MVP 的 3 个训练模块（句子工坊、作文城堡、阅读峡谷）平均铺开**。前端的 UI 改造也遵循同样原则——"先建立最小设计系统，优先改造主路径"。

这是一个正确的"深度优先"策略。与其做出三个勉强能点的页面，不如把最核心的一条路径做到能让真实孩子完成一次有意义的作文修改体验。

**但这个决策有诚实的代价需要承认**：

1. **其他功能模块处于"骨架可用但体验未打磨"状态**。阅读峡谷和句子工坊在 MVP 阶段已有基础功能实现，但 V0.2 没有投入 UI 改造资源。如果内测时孩子从 Dashboard 点进这些模块，会看到与作文页视觉风格不一致的界面——这不是 bug，而是有意未覆盖的范围。
2. **句子工坊的定位矛盾**。原 MVP spec 将句子工坊定位为高频轻练（5-8 分钟），是维持日常训练频率的关键模块。V0.2 将其降级为"修改预热入口"，spec 明确说"不作为硬验收链路"。这意味着孩子从 Dashboard 只能进入作文（10-15 分钟重任务），没有真正的轻量选项。短期可接受，但连续多天的内测中会暴露"只有重任务没有轻练"的体验问题。

**建议**：
- 在 V0.2 完成定义中为句子工坊增加一条最低验收条件："句子工坊有一个可点击的入口，孩子能完成一次句子升级并看到反馈"——不要求精美 UI，但确保功能链路不断。
- 对阅读峡谷和诊断页等其他非主路径页面，在发布说明中明确标注"本版本未覆盖 UI 改造"，管理内测用户的预期。

### 1.3 多画像验证缺口

V0.2 硬验收链路围绕小宇画像，AI 质量评审也只覆盖了小宇。但 MVP spec 定义了 4 个孩子画像（1 真实 + 3 模拟），并明确要求"3 个模拟孩子应能展示不同画像：表达空泛型、作文结构薄弱型、阅读概括薄弱型"。

当前状态：3 个模拟孩子的能力画像数据由 seed 脚本创建，但没有人实际验证过——选了不同孩子后，Dashboard 的推荐任务、能力条、AI 教练文案是否真的因画像不同而有差异？

**验收条件**：
1. 分别选择 3 个模拟孩子，各自查看 Dashboard 页
2. 验证每个孩子的能力条展示出不同的强弱项分布（如表达空泛型孩子的"写具体力"明显低于其他维度）
3. 验证每个孩子的推荐任务 focus 文案不同（如结构薄弱型推荐"段落顺序和过渡"相关的训练重点）
4. 为每个模拟孩子生成一份阶段报告，确认报告中的薄弱点和建议与画像匹配

**CEO 结论**：产品质量方向正确，深度优先策略合理。需要在句子工坊可用性和多画像验证上补充明确的验收条件。LLM provider 配置模式对内测阶段够用，但商业模式（谁为 AI 调用付费）和成本可见性需要在灰度前给出答案。

---

## 2. Learning Designer Review

### 2.1 学习闭环完整性

```text
诊断 → 能力画像 → 推荐任务 → 训练 → AI 反馈 → 修改 → 结算 → 画像更新 → 下一轮推荐
```

这个闭环在 MVP 中已完整实现，V0.2 强化了其中最关键的一环（作文修改的 AI 反馈质量）。

**通过。**

### 2.2 反代写设计的有效性

三层防线（Prompt 层 + 产品层 + 检测层）设计合理。真实 LLM 测试确认 AI 不输出完整可提交作文，点评只给修改任务。这是产品最核心的差异化优势。

**但有一个隐患**：`convert_ghostwriting_request` 的检测是在 `essay_feedback` 函数中进行的，不是在 essay route 入口处进行的。这意味着如果孩子在"写初稿"阶段就输入了"帮我写一篇作文"，这个检测会在提交后才触发，而不是在输入阶段就拦截。UX 上孩子可能已经写了（或粘贴了）内容才发现被拒绝。

**建议**：后续版本考虑在前端添加轻量检测提示（如"这里应该写你自己的作文哦"），但当前优先级不高。

**通过，有后续改进建议。**

### 2.3 AI 反馈的学习设计质量

真实 LLM 测试（DeepSeek v4 flash）结果显示：

- 优点具体（"有清晰的事件起点和终点，叙事完整"）
- 修改任务可执行（"请用 2-3 句话描写你一开始害怕时的样子和感受"）
- 二稿对比引用了真实改动证据

**主要问题**：AI 给出了 3 个修改任务，而不是 spec 期望的 1 个最小可执行任务。四年级孩子面对 3 个修改选项可能感到困惑或压力。QA 结论已建议调整 prompt。

**学习设计建议**：
1. Prompt 中明确要求"只给出 1 个最小、最重要的修改任务"
2. 但如果孩子选择了多个任务，系统不应阻止——自主选择也是一种学习
3. 结算时应区分"完成全部任务"和"完成部分任务"的反馈语气

### 2.4 能力画像的学习科学性

6 维能力 -> 3 维映射的设计合理。但当前能力更新机制（规则 + LLM 混合）在真实 LLM 测试中未得到充分验证——QA 只验证了 feedback 和 comparison，没有追踪到 ability profile 的实际数值变化是否合理。

**建议**：下一轮 AI 质量评审应同时检查"能力画像数值是否合理变化"和"结算 XP 是否与修改质量相关"。

**Learning Designer 结论**：学习设计骨架坚固，反代写防线有效。Prompt 需要精调以控制修改任务数量。能力画像的实际更新质量需要验证。

---

## 3. Child User Experience Review

### 3.1 主路径 UI 质量

V0.2 的 UI 改造已将主路径从裸 HTML 提升到有设计系统的基础产品级：

- 暖色调（`--wen-bg: #fff8e7`，`--wen-sun: #ffd166`，`--wen-orange: #ff8a4c`）
- 卡片式布局（`rounded-lg border bg-white shadow-sm`）
- 清晰的行动按钮（橙色 CTA button）
- Lucide 图标（`PenLine`, `Timer`, `Sparkles`, `CheckCircle2`）

整体感觉温暖、友好、不过度幼稚。**符合 MVP spec 要求。**

### 3.2 UI Bug：TaskCards 标签重复

`TaskCards.tsx:38-39`：

```tsx
<h3 className="mt-1 text-lg font-bold">
  {label}：{task.title}
</h3>
```

这会导致显示"主线：作文城堡"，而上一行的 `<p>` 标签已经显示了 "主线"。结果是"主线"出现了两次。

**修复**：`h3` 应该只显示 `{task.title}`，不需要再加 `{label}：` 前缀。或者保留 h3 中的完整格式，去掉上面的 `<p>{label}</p>`。

**严重度**：低。不影响功能，但降低信息架构的清晰度。

### 3.3 儿童友好的状态文案

加载和错误状态的文案质量良好：
- "AI 教练正在读你的初稿" ✓
- "这次提交没有成功。先别急，检查一下网络后再试一次。" ✓

**通过。**

### 3.4 缺失：页面间导航和信息架构

当前产品缺少用户在不同页面之间移动的合理导航机制。具体表现为：

- **没有全局导航栏或面包屑**。孩子从 Dashboard 进入作文页后，没有可见的"返回首页"或"回到小文星球"入口。如果孩子完成了作文修改，想回到 Dashboard 看能力变化，不知道点哪里。
- **家长和孩子页面之间没有切换路径**。家长看了孩子 Dashboard 后想去看报告，或者看了报告想回 Dashboard，都需要手动改 URL。
- **页面之间是孤岛**。每个页面（Dashboard / 作文 / 报告）各自独立，用户无法感知自己在产品中的位置。

这不是 V0.2 spec 要求的功能，但它是内测可用性的一个真实断层。QA 报告中已经反映了这个问题的症状：测试者需要"直接打开 `/children/s1/essay` 继续作文流程"——普通用户不会有这个知识。

**严重度**：中等。孩子可能在页面间"迷路"，依赖浏览器后退按钮。这会破坏学习闭环的连贯体验。

**建议**：
- 最低方案：在每个主路径页面顶部添加一个简单的返回链接（如"← 回到小文星球"），不需要完整导航系统。
- 这是 P1 级别的修复，不应阻塞首次内测，但应在内测开始前解决。

### 3.5 缺失：句子工坊入口可用性

QA 报告明确指出"Dashboard 没有可用的'去写作文'链接；页面上的'作文城堡'是占位链接"。这是一个阻塞性问题——如果主路径的入口从 Dashboard 不可达，孩子根本无法开始作文流程。

但这个问题的根源需要确认：是 recommendations API 没有正确返回 essay 类型的任务？还是 TaskCards 组件的链接生成有问题？

从代码来看，`TaskCards.tsx:25-28` 对 essay 类型任务会生成正确的 `/children/${studentId}/essay` 链接。问题可能在 API 返回的任务类型不匹配，或 Dashboard 页面获取数据失败。

**需要立即验证**：启动本地服务，查看 Dashboard 是否能正常渲染作文任务入口。

### 3.6 修改任务复选框的 UX

当前每个修改任务是 checkbox，孩子可以勾选/取消。这是一个好的设计——孩子可以选择完成哪些任务。但有两个 UX 建议：

1. **默认行为**：所有任务应该默认勾选（"AI 建议的都做"），孩子可以主动取消不想做的。这比全部不勾选更符合"鼓励尝试"的理念。
2. **结算反馈**：当前结算只显示 XP 和等级，没有体现"完成了几个任务"的反馈。建议在结算文案中加入"完成了 2 个修改任务！"

**Child UX 结论**：主路径 UI 基线达标。存在两个具体 bug（TaskCards 标签重复 + Dashboard 作文入口可能不可达）。页面间导航缺失是一个信息架构层面的体验断层，孩子可能在页面间迷路。句子工坊入口不可用导致只有重任务没有轻练。

---

## 4. Parent User Experience Review

### 4.1 报告信息架构

家长报告页 (`parent/[studentId]/report/page.tsx`) 的信息架构清晰：
1. 练习概况
2. 这次看见的进步
3. 最有证据的一处修改
4. 下一步

**符合 MVP spec 中家长报告应回答的 5 个问题**（练了什么、哪里进步、薄弱点、下一步、修改前后变化）。

### 4.2 报告语气

`reports.py` 中报告的默认文案："继续做 1 次句子加细节"、"完成 1 次作文二稿修改"——语气专业、温和、不制造焦虑。

**通过。**

### 4.3 缺失：多孩子切换

MVP spec 提到了家长可以在不同孩子档案间切换（"必要时切换到其他模拟孩子档案"）。当前实现中，家长入口是 `app/page.tsx` 的"进入家庭内测"，但进入后没有看到孩子切换 UI。这对 4 孩子画像的内测场景是功能缺失。

**建议**：在家长 Dashboard 或报告页增加孩子切换下拉菜单，或在导航栏显示当前孩子名称和切换入口。

### 4.4 报告数据的完整性

`reports.py` 的 report content builder 现在使用了 `revision.completed_tasks`、`revision.ai_feedback` 中的 evidence 等具体数据，不再是泛泛文字。这是一个重要进步。

**Parent UX 结论**：报告信息架构和语气达标。多孩子切换是已知缺失。报告数据现在有具体证据支撑，不再是空洞鼓励。

---

## 5. Engineering Manager Review

### 5.1 架构决策

**Provider DI 模式正确**。`get_llm_provider` 通过 FastAPI dependency injection 注入，route 层不直接实例化 `MockLLMProvider`。路由测试使用 `dependency_overrides[get_llm_provider]` 注入 fake provider——这是 FastAPI 的最佳实践。

**LLMProviderResponse dataclass 设计合理**。同时返回 `parsed_json`、`raw_response`、`provider`、`model`，分离了"系统解析结果"和"原始输出"，便于调试和日志记录。

**通过。**

### 5.2 韧性设计

```text
build prompt → provider.complete_json → capture raw response
→ Pydantic schema validation → retry on invalid output / error
→ return valid parsed output → if retries exhausted, return fallback
→ write LLMCallLog
```

这个流程在 `run_validated_llm_task` 中实现，MAX_LLM_ATTEMPTS=2。测试覆盖了：
- `invalid -> valid` retry ✓
- `always invalid` fallback ✓
- `raising provider` fallback ✓

降级反馈都是儿童友好的保守文案，不中断作文流程。**设计良好。**

### 5.3 测试覆盖

| 层级 | 覆盖 | 状态 |
|------|------|------|
| 后端 model 测试 | LLMCallLog/EssayVersion 新字段 | ✓ |
| 后端 migration 测试 | 迁移文本断言 | ✓ |
| 后端 route DI 测试 | dependency_overrides 注入 fake provider | ✓ |
| 后端 resilience 测试 | retry/fallback/exception | ✓ |
| 后端 workflow API 测试 | revision metadata 持久化 | ✓ |
| 后端 report 测试 | revision evidence 反映到报告 | ✓ |
| 前端 unit 测试 | Dashboard 作文入口、essay flow | ✓ |
| 前端 E2E | 小宇 essay revision spine | ✓ |

**覆盖充分。通过。**

### 5.4 数据模型质量

`LLMCallLog` 补齐了 provider、model、prompt_version、raw_response、retry_count 字段。`EssayVersion` 补齐了 duration_seconds、completed_tasks、skipped_tasks、llm_call_log_id。这些字段支持了 AI 质量复盘的最小需求。

**一个设计点**：`LLMCallLog.raw_response` 使用 `sa.Text()` 而非 `sa.String()`，支持长文本。`completed_tasks` 和 `skipped_tasks` 使用 `sa.JSON()`，支持列表存储。类型选择正确。

**通过。**

### 5.5 代码组织

实现计划按 9 个顺序任务组织，每个任务有 review gate 和独立的 commit。Git log 显示 9 个任务中有 8 个任务对应的 commit 清晰可追溯（Task 1-8）。

**一个改进点**：Task 1 部分被拆成了两个 commit（`fe767fd` 和 `a4f89ad`），而非计划中的一个。这不影响质量，但说明实际实现与计划有微小偏离。

### 5.6 LLM Provider 配置的规模化缺口

当前 LLM provider 的配置方式是开发者在后端 `.env` 中填写自己申请的 API key：

```text
LLM_PROVIDER=http
LLM_API_KEY=sk-xxxxxxxx  ← 开发者个人 key
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.example.com/v1
```

这个模式在以下场景**完全够用**：
- 本地开发（默认 mock，开发者自己切换 http 测试）
- 内部 QA（一个人用真实 key 跑一轮评审）
- 极早期家庭内测（开发者把 key 配在部署环境里，几个内测家庭共用）

但在以下场景**会出问题**：

1. **成本归属不可追踪**。所有用户的 LLM 调用走同一个 API key，无法知道哪个用户消耗了多少 token。`LLMCallLog` 记录了每次调用的输入输出，但没有关联到 `student_id` 或 `parent_id`。如果一个内测家庭大量使用，开发者的 key 账单会涨，但无法溯源。

2. **没有 rate limiting 和滥用防护**。当前路由层没有任何频率限制。一个客户端脚本可以在短时间内触发大量 LLM 调用，耗尽 API key 的配额。

3. **商业模式未定义**。作为面向家庭的产品，长期必然面临"谁为 LLM 调用付费"的问题——是平台承担成本（订阅制）、还是允许家长配置自己的 key（自带给）？当前架构假设的是前者（平台级 key），但产品 spec 没有讨论过这个问题。

4. **部署时的配置管理**。`.env` 文件不进入 git，这正确。但对于 Docker/云部署，需要通过容器环境变量或 secret manager 注入——目前 `config.py` 的 `Settings` 类已经支持从环境变量读取，这一点基础是好的。

**当前阶段的建议**：

| 阶段 | 方案 | 风险 |
|------|------|------|
| V0.2 内部开发 | `.env` + 开发者个人 key | 无 |
| 2-3 个家庭内测 | 部署环境变量 + 开发者 key | 低。用量可控，成本可接受 |
| 10+ 家庭灰度 | 需要在 `LLMCallLog` 中增加 `student_id` 字段，按用户统计 token 消耗 | 中。无成本可见性则无法决策 |
| 公开发布 | 需要决定商业模式 + 实现 usage tracking + rate limiting | 高。这是发布阻塞项 |

**建议**：在 V0.2 完成定义或下一版 spec 中，为 `LLMCallLog` 增加 `student_id` 字段（可为空，因为有些调用如 seed 脚本不关联学生）。这是成本可见性的最小实现，不影响当前功能，但为后续规模化铺路。

**Engineering Manager 结论**：架构决策正确，韧性设计完善，测试覆盖充分，数据模型合理。V0.2 的深度优先策略（只打磨作文链路，冻结其他模块）在工程上是明智的——用最少的代码改动验证了最关键的质量机制。LLM provider 的配置模式对当前阶段够用，但需要在灰度前解决成本可见性问题。工程质量达到 V0.2 质量脊柱 spec 的要求。

---

## 6. QA / Release Manager Review

### 6.1 V0.2 完成定义对照

对照 `specs/2026-05-14-wenlingo-v0.2-quality-spine-design.md` §10 的 6 条完成定义：

| # | 完成定义 | 状态 | 证据 |
|---|----------|------|------|
| 1 | 小宇画像走完整作文修改闭环，主路径 UI 不裸 | ⚠️ 待验证 | QA 报告提到 Dashboard 没有可用作文入口，需直接 URL 访问 |
| 2 | 作文点评/二稿对比可切换 mock/真实 LLM | ✅ | LLM_PROVIDER 配置已实现，真实 LLM 测试已完成 |
| 3 | LLM 输出有 schema validation/retry/fallback/log | ✅ | `run_validated_llm_task` 实现，测试覆盖 |
| 4 | 至少一次真实 LLM 测试并完成 AI 质量人工评审 | ✅ | `qa/2026-05-14-v0.2-ai-quality-review.md` |
| 5 | 后端/前端/E2E 测试覆盖主验收点 | ✅ | 测试全部通过 |
| 6 | 根据真实 LLM 评审结果调整 prompt/schema/体验 | ❌ 未执行 | QA 结论是"需调整 prompt"，但尚未执行 |

### 6.2 QA 报告质量评估

`qa/2026-05-14-v0.2-ai-quality-review.md`：
- 记录了真实的 provider/model/prompt_version ✓
- 逐项评估了 AI 点评质量（6 个维度）✓
- 逐项评估了二稿对比质量（3 个维度）✓
- 记录了系统行为（retry/fallback/log）✓
- 给出了明确的人工结论和建议 ✓

**QA 报告格式规范，评审维度完整。通过。**

### 6.3 阻塞性问题

1. **Dashboard 到作文页的入口不可达**（QA 报告指出）。这阻塞了 V0.2 完成定义 #1。需要根因分析：是 API 返回数据问题还是前端渲染问题。

2. **Prompt 调整未执行**（完成定义 #6）。QA 结论是"需调整 prompt"，建议将初稿点评约束为优先输出 1 个最小可执行 revision_task。这个调整应在真实家庭内测前完成。

3. **页面间导航缺失**。当前没有全局导航栏、面包屑或返回链接。孩子和家长在页面间移动只能依赖浏览器后退按钮或手动输入 URL。虽然 V0.2 spec 未要求完整导航系统，但对真实内测家庭来说，页面孤岛体验会显著增加困惑和挫败感。

### 6.4 发布前检查清单

- [ ] 修复 Dashboard 作文入口不可达问题
- [ ] 根据 AI 质量评审调整 essay_feedback prompt（约束为 1 个最小修改任务）
- [ ] 重新运行一次真实 LLM 测试，确认 prompt 调整效果
- [ ] 添加页面间最小导航（每个主路径页面至少有一个返回链接）
- [ ] 修复 TaskCards 标签重复 bug
- [ ] 验证 3 个模拟孩子画像的 Dashboard 和报告差异化：
  - [ ] 表达空泛型：能力条显示"写具体力"为短板
  - [ ] 结构薄弱型：推荐任务 focus 涉及段落结构
  - [ ] 概括薄弱型：能力条显示"读懂力"为短板，报告薄弱点涉及概括
- [ ] 句子工坊至少有一个可用入口（不要求精美 UI）
- [ ] 端到端验证：从 Dashboard 点击 → 完成作文闭环 → 查看家长报告（全部在浏览器中操作，不手动输入 URL）

**已知缺口（不阻塞 V0.2，但需在灰度前解决）**：
- [ ] `LLMCallLog` 增加 `student_id` 字段，实现按用户统计 LLM 消耗
- [ ] 定义 LLM 成本的商业模式（平台承担 / 家长自带给 / 混合）
- [ ] 路由层增加基础 rate limiting

### 6.5 版本命名

当前 git 状态显示所有 commit 在 main 分支上。V0.2 质量脊柱的改动已经合并。建议在发布真实家庭内测版时打 tag `v0.2-internal-test`。

**QA / Release Manager 结论**：V0.2 的后端和测试基础设施已达到发布质量。前端主路径有一个阻塞性入口问题需要修复。页面间导航缺失、多画像验证未执行、Prompt 调整未完成——这三个问题加起来，意味着当前版本还不能直接交给一个普通家庭内测。距离"可让真实孩子内测"还差一次集中冲刺（修复入口 + 调整 prompt + 补导航 + 验证多画像 + 重测）。

---

## 7. 综合评审结论

### 7.1 每个视角的一句话总结

| 视角 | 结论 |
|------|------|
| CEO | 方向正确，深度优先策略合理。但范围收窄有诚实代价：其他模块处于骨架状态。多画像验证需要补充。 |
| Learning Designer | 学习闭环坚固，反代写有效。Prompt 需要精调控制任务数量（3→1）。 |
| Child UX | 主路径 UI 基线达标。页面间导航缺失导致孤岛体验。Dashboard 入口 bug 和 TaskCards 标签重复需修复。 |
| Parent UX | 报告有具体证据，不再是空洞鼓励。多孩子切换缺失。 |
| Engineering | 架构、韧性、测试均达标。LLM provider 配置模式对内测够用，但成本可见性（按用户统计 token 消耗）是灰度前的必修课。 |
| QA / Release | 距离真实内测还差一次小迭代：修复入口 + 调整 prompt + 补导航 + 重测。 |

### 7.2 优先级排序

**P0 — 必须修复才能内测**：
1. Dashboard 作文入口不可达（根因分析 + 修复）
2. 调整 essay_feedback prompt（限制为 1 个最小修改任务）

**P1 — 内测前应完成**：
3. 添加页面间最小导航（至少每个主路径页面有"回到小文星球"链接）
4. 修复 TaskCards 标签重复
5. 验证 3 个模拟孩子差异化画像（Dashboard 能力条 + 推荐任务 focus + 报告薄弱点）
6. 句子工坊至少有一个可用入口

**P2 — 内测后迭代**：
7. 修改任务默认勾选
8. 多孩子切换 UI
9. 结算中体现任务完成数量
10. 前端轻量代写检测提示

### 7.3 产品就绪度评分

```
                MVP    V0.2   目标
学习闭环        ████████  ████████  ████████
AI 反馈质量     ████      ████████  ████████
孩子端 UI       ██        ██████    ████████
家长端 UI       ███       ██████    ████████
工程质量        ██████    ████████  ████████
内测就绪度      ███       ██████    ████████
```

V0.2 在各维度上相较 MVP 有显著提升，尤其在 AI 反馈质量和工程质量两个维度已达到目标。孩子端 UI 和家长端 UI 还需打磨。内测就绪度接近但尚未完全达到。

### 7.4 推荐下一步行动

1. **立即（P0）**：修复 Dashboard 入口 bug + 调整 essay_feedback prompt
2. **今天**：添加页面间最小导航（返回链接）+ 修复 TaskCards 标签重复 + 重跑真实 LLM 验证
3. **明天**：验证 3 个模拟孩子差异化画像 + 句子工坊入口可用性
4. **明天结束前**：完整 E2E 链路验证（浏览器操作，不手动改 URL）
5. **本周末**：开始真实家庭内测

---

## 附录：文件验证

所有引用文件均已读取确认存在：
- `specs/2026-05-06-wenlingo-mvp-design.md` ✓
- `specs/2026-05-14-wenlingo-v0.2-quality-spine-design.md` ✓
- `plans/2026-05-06-wenlingo-mvp-implementation.md` ✓
- `plans/2026-05-14-wenlingo-v0.2-quality-spine-implementation.md` ✓
- `qa/2026-05-14-v0.2-ai-quality-review.md` ✓
- `ai_chinese_literacy_prd_v_0_1.md` ✓
- `docs/ai-collaboration-protocol.md` ✓
- `CLAUDE.md` ✓
- `AGENTS.md` ✗ （文件不存在）
