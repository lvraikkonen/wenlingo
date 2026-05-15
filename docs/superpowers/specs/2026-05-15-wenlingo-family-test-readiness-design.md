# WenLingo Family Test Readiness Design

日期：2026-05-15

## 1. Goal

本轮目标是把 WenLingo 从“V0.2 作文质量脊柱已完成”推进到“普通家庭可以独立完成一次内测体验”。真实家庭不应依赖开发者陪跑、手动输入深层 URL 或理解哪些页面尚未完成；孩子和家长应能从家庭入口进入，选择或切换孩子，完成作文主线和句子快练，看到结算与报告，并在未完成模块中看到友好的“施工中”提示。

这不是公开发布版，也不是完整家庭账号系统。本轮仍是 MVP 打磨，但验收标准从“单条小宇作文链路可跑通”提升为“一个 demo family 的 4 个孩子画像在浏览器内可被理解、可被切换、可被验证”。

## 2. Source Documents

- `specs/2026-05-06-wenlingo-mvp-design.md`
- `specs/2026-05-14-wenlingo-v0.2-quality-spine-design.md`
- `plans/2026-05-14-wenlingo-v0.2-quality-spine-implementation.md`
- `specs/2026-05-15-wenlingo-mvp-gstack-review.md`
- `qa/2026-05-14-v0.2-ai-quality-review.md`
- `AGENT.md`
- `CLAUDE.md`

## 3. Product Scope

Hard scope:

- Add a lightweight global topbar / app shell for the family-test experience.
- Productize 4 child profiles through a visible current-child switcher.
- Ensure Dashboard cards can enter both essay and sentence tasks.
- Fix the essay path issues called out by review: Dashboard entry, page navigation, duplicate task labels, and essay feedback prompt returning too many revision tasks.
- Polish Sentence Workshop into a complete child-friendly light task, not just a bare functional page.
- Upgrade Sentence Workshop AI to the same quality spine level as essay feedback.
- Add `student_id` to LLM call traceability.
- Add configurable minimum daily LLM usage protection for deployed internal tests.
- Provide friendly “施工中” states for planned but unfinished modules such as Reading Canyon.
- Verify 4 child profiles for Dashboard, recommendation, and report differentiation.
- Run one real LLM QA pass for 小宇 essay feedback / comparison and one real LLM QA pass for 小宇 sentence feedback.

Explicit non-goals:

- No account, authentication, invitation, or family permission system.
- No full usage analytics dashboard.
- No token, latency, or cost accounting fields beyond the minimum `student_id` traceability.
- No long-term multi-child comparison report.
- No complete Reading Canyon rewrite.
- No new training modules.
- No complex gamification system, pet system, map progression, or badge tree.
- No AI-generated final essays or sample essays that children can submit directly.

## 4. Information Architecture

The main family-test pages should share a lightweight app shell after the family entry point. The shell includes:

- Product identity: `小文星球`.
- Current child display, for example `当前孩子：小宇`.
- Child switcher for the 4 seeded/demo child profiles.
- Links to current child Dashboard, Essay Castle, Sentence Workshop, and Parent Report.

The child switcher is a demo-family navigation affordance, not an account system. Switching children should take the user to the selected child’s Dashboard so the user can immediately see that child’s ability profile and recommendation.

Primary routes must feel connected:

- Family entry opens the demo family and makes the available child profiles visible.
- Dashboard highlights the recommended essay and sentence tasks.
- Essay and sentence task pages include a clear way back to Dashboard and to the parent report.
- Parent report includes a clear way back to the current child Dashboard and allows switching to another child.
- Planned-but-unfinished module links open a friendly construction state instead of a dead route, placeholder link, or raw 404.

## 5. Friendly Construction States

Reading Canyon and other planned modules should not disappear, because the product map still helps explain the future learning world. They also should not look broken.

For unfinished planned modules, show a child-friendly state such as:

- Title: `🚧 阅读峡谷施工中`
- Body: `这里还在建设。小文星球会先把今天推荐的作文和句子任务陪你做好。`
- Primary action: `回到小文星球`
- Secondary action when relevant: `去完成今日推荐`

The exact emoji can be implemented as text. The key requirement is that the page communicates “planned but not ready” warmly and gives the child a next action.

## 6. Learning Experience

The two child tasks have distinct roles:

- Essay Castle is the 10-15 minute heavy task.
- Sentence Workshop is the 5-8 minute light task.

Both tasks should reinforce the same learning principle: improve expression by making writing more concrete.

### Essay Castle

The essay flow remains:

```text
draft -> AI feedback -> one revision task -> revision -> comparison -> settlement -> report evidence
```

Changes for this round:

- The `essay_feedback` prompt should strongly prefer exactly one smallest, most important revision task.
- The UI should not block if a provider returns more than one valid task, but the expected happy path is one task.
- Revision task checkboxes should default to selected.
- Settlement should reflect the number of completed revision tasks.
- Parent report should preserve concrete evidence from the revision comparison.
- Children should see clear loading, fallback, and error states without technical details.

### Sentence Workshop

The sentence flow is:

```text
source sentence -> upgraded sentence -> AI feedback -> settlement -> next task / Dashboard
```

Changes for this round:

- Apply the same baseline visual system as the essay path.
- Provide child-friendly labels, hints, and example-like prompts without writing the child’s answer for them.
- Use friendly loading and error copy.
- Show encouragement, one specific improvement point, problem monster if available, XP, and level after completion.
- Provide a clear next action back to Dashboard or parent report.

## 7. AI Quality Design

Essay AI already has the V0.2 quality spine:

```text
route -> provider dependency -> prompt payload -> provider.complete_json
-> schema validation -> retry/fallback -> LLMCallLog
```

Sentence Workshop should be upgraded to this same pattern. The sentence route must not instantiate `MockLLMProvider()` directly. It should receive the provider through FastAPI dependency injection and use the shared validated LLM task runner.

AI tasks covered in this round:

- `essay_feedback`
- `essay_revision_comparison`
- `sentence_upgrade_feedback`

For `sentence_upgrade_feedback`, define a schema-valid fallback that is safe, encouraging, and useful when the provider fails or returns invalid JSON. The fallback should preserve the child’s workflow rather than blocking completion.

Prompt behavior:

- Essay feedback should ask for one minimal revision task.
- Sentence feedback should encourage the child and identify a concrete improvement, not rewrite the sentence for them.
- Both prompt families must keep the anti-ghostwriting posture: the system helps children revise, it does not submit finished writing for them.

## 8. Data And Usage Protection

`LLMCallLog` should gain a nullable `student_id` field. It should be populated for essay and sentence task calls that happen inside a student workflow.

The minimum useful traceability for this round:

- `student_id`
- `task_type`
- `provider`
- `model`
- `prompt_version`
- `input_summary`
- `raw_response`
- `output_json`
- `validation_ok`
- `error_message`
- `retry_count`
- `created_at`

The implementation should not add token, latency, or cost fields in this round.

Add configurable minimum daily usage protection:

- Default local and automated-test behavior is disabled.
- Deployment can enable it with environment configuration.
- Limit should apply at least by `student_id + task_name` for real LLM calls.
- When over limit, the child-facing response should be friendly and safe. It can either use a conservative fallback or return a product-level message such as `今天的 AI 教练次数先用完啦，我们先把已经拿到的建议认真改一改。`
- Technical quota details must not be exposed to children.

Suggested config names for implementation planning:

```text
LLM_DAILY_LIMIT_ENABLED=false
LLM_DAILY_LIMIT_PER_STUDENT_TASK=5
```

The implementation plan may adjust exact names if the existing settings style suggests a better convention.

## 9. Multi-Profile Validation

The 4 child profiles should be visible and testable. The exact seed names can follow existing seed data, but the validation must cover these profile types:

- 小宇 / primary realistic child profile.
- 表达空泛型.
- 作文结构薄弱型.
- 阅读概括薄弱型.

For each child, QA should verify:

- Dashboard ability bars show a different strength/weakness shape.
- Recommended task focus differs in a way that matches the child profile.
- Parent report weak points and suggestions match the profile.

This does not require real LLM calls for all 4 children in this round. The real LLM QA matrix stays intentionally small:

- 小宇 essay feedback and revision comparison: one complete run.
- 小宇 sentence feedback: one complete run.

## 10. Testing Strategy

Backend tests should cover:

- `LLMCallLog.student_id` model and migration behavior.
- Essay LLM logging still records student context.
- Sentence route uses provider dependency rather than direct mock instantiation.
- Sentence AI validation retry and fallback.
- Daily limit disabled by default.
- Daily limit enabled path blocks or falls back safely after the configured threshold.
- Reports can use recent essay and sentence evidence without losing existing behavior.

Frontend tests should cover:

- Topbar renders current child and navigation links.
- Child switcher routes to the selected child Dashboard.
- Dashboard task cards enter essay and sentence pages.
- Task card labels do not duplicate category labels.
- Essay revision tasks default to selected and settlement reflects completed task count.
- Sentence Workshop shows feedback, settlement, loading, and friendly error states.
- Construction page/state renders for unfinished planned modules.
- Parent report navigation returns to the current child Dashboard.

E2E should cover browser navigation without manual URL editing:

```text
family entry
-> choose/switch child
-> 小宇 Dashboard
-> enter essay from Dashboard
-> complete essay feedback, revision, comparison, settlement
-> return to Dashboard
-> enter sentence workshop
-> complete sentence feedback and settlement
-> open parent report
-> open unfinished module and return from construction state
```

Manual QA should produce records for:

- 4 child profile differentiation.
- 小宇 real LLM essay quality.
- 小宇 real LLM sentence quality.
- Whether retry or fallback triggered.
- Whether prompts avoided ghostwriting and gave actionable revision/upgrade advice.

## 11. Completion Definition

This round is complete when all of the following are true:

1. A normal family tester can navigate the main demo-family flow in the browser without manually editing URLs.
2. The global topbar shows the current child, supports switching among the 4 demo child profiles, and links to Dashboard, Essay Castle, Sentence Workshop, and Parent Report.
3. Dashboard can start both essay and sentence tasks.
4. Essay feedback normally returns one minimal revision task, task selection defaults to selected, and settlement reflects task completion.
5. Sentence Workshop is visually and behaviorally polished enough to be a real light task.
6. Essay and sentence AI calls can use the configured provider, validate schemas, retry, fall back, and log traceability.
7. `LLMCallLog.student_id` is recorded for student workflow calls.
8. Configurable daily LLM usage protection exists and is disabled by default.
9. Reading Canyon and other unfinished planned modules show friendly construction states.
10. Automated backend, frontend, and E2E tests cover the main acceptance points.
11. QA records verify the 4 child profiles differ in Dashboard / recommendations / report.
12. Real LLM QA records exist for 小宇 essay and 小宇 sentence flows.

## 12. Implementation Planning Notes

The implementation plan should be sequential with review gates. A likely order is:

1. Add data and config support for `LLMCallLog.student_id` and daily LLM limits.
2. Upgrade sentence AI to the shared validated LLM task runner.
3. Adjust essay feedback prompt and task completion behavior.
4. Add app shell / topbar and child switching.
5. Fix Dashboard task entries and TaskCards labeling.
6. Polish Sentence Workshop UI and states.
7. Add friendly construction states.
8. Update parent report and multi-profile navigation.
9. Add/refresh E2E and QA documentation.

Do not begin implementation from this design until the written spec has been reviewed and approved.
