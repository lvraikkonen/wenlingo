# WenLingo Family Test Readiness Manual QA

日期：2026-05-15
执行人：Codex
环境：local browser, FastAPI localhost:8000, Next.js localhost:3000

## 四画像验证

| 孩子 | 能力值 | Recommendation focus | Report weak point | 结果 |
| --- | --- | --- | --- | --- |
| 小宇 | reading_power 40, specific_writing_power 47, revision_power 41 | main: 把细节写具体; quick: 加动作或神态 | 继续保持细节和修改练习 | pass |
| 小晴 | reading_power 40, specific_writing_power 31, revision_power 34 | main: 把细节写具体; quick: 加动作或神态 | 表达还可以更具体 | pass |
| 小川 | reading_power 40, specific_writing_power 42, revision_power 32 | main: 把选材和结构说清楚; quick: 加动作或神态 | 作文结构还需要更清晰 | pass |
| 小禾 | reading_power 27, specific_writing_power 41, revision_power 40 | main: 先把阅读内容概括清楚; quick: 加动作或神态 | 阅读概括可以继续练 | pass |

## 小宇 Real LLM Essay QA

- Provider: http
- Model: deepseek-v4-flash
- Prompt version: v0.2-quality-spine-2026-05-14
- Returned revision task count: 1
- Anti-ghostwriting verdict: pass. The response asked for one bounded revision, "将'后来我会了'扩写成两句话，描述学习过程中的一个具体步骤或转折。", instead of rewriting the whole essay.
- Comparison evidence: pass. The revision comparison cited student-written details: "紧紧抓着车把，手心都出汗了", "摇摇晃晃骑过花坛", and "开心得跳了起来".
- Retry status: no retry observed; LLMCallLog retry_count was 0 for essay_feedback and essay_revision_comparison.
- Fallback status: no fallback observed; both essay LLMCallLog rows had validation_ok=true and empty error_message.

## 小宇 Real LLM Sentence QA

- Provider: http
- Model: deepseek-v4-flash
- Prompt version: v0.2-quality-spine-2026-05-14
- Encouragement verdict: pass. The feedback praised the student's added time, place, concrete object, and simile.
- Concrete-improvement verdict: pass. The feedback specifically compared "很美" with the concrete image "清晨公园荷叶水珠" and the simile "像小灯泡".
- Anti-rewrite verdict: pass. The next step suggested adding one sensory detail, such as sound, rather than replacing the student's sentence.
- Retry status: no retry observed; LLMCallLog retry_count was 0 for sentence_upgrade_feedback.
- Fallback status: no fallback observed; the sentence LLMCallLog row had validation_ok=true and empty error_message.

## Navigation QA

- No manual URL editing after family entry: pass. Playwright E2E used only the initial `page.goto("/")`; subsequent movement used visible links.
- Child switcher routing: pass. 小晴 switcher link resolved to `/children/s2` from 小宇 Dashboard.
- Dashboard task-card entry: pass. The sentence task was entered from the Dashboard `句子工坊` task card via the visible `开始任务` link.
- Essay entry: pass. In the current pre-assessment Dashboard state, 作文城堡 was entered via the visible top navigation link.
- Reading Canyon construction-state next action: pass. `阅读峡谷` opened `阅读峡谷施工中`, and `回到小文星球` returned to 小宇 Dashboard.

## Verdict

pass with follow-up

Family-test readiness passed in a fresh local QA database; follow up by refreshing or migrating stale local SQLite files such as `playwright-e2e.db` before reusing them for E2E.
