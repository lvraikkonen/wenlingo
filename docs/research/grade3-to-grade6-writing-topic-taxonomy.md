# 3-6 年级课内同步作文题型分类

Date: 2026-06-25
Source: `docs/research/writing-tasks-grade3-grade6/` 中 57 张习作截图
Purpose: 为 Writing Castle V0.6b+ 的 `TopicType`、`ScaffoldTemplate`、素材卡 slots 和提纲结构提供 3-6 年级整体依据

---

## 研究口径

- 本次统计按截图集中实际收录的 57 个习作题计算。
- 三下、四下、五下部分册次存在综合性学习单元，因此不是每个单元都有独立习作截图。
- 六下文件夹只有 4 张图，且缺少 `IMG_4870`。需要确认是否缺少《心愿》等六下习作截图；本研究未将未收录截图计入覆盖率，只在风险中提示需要补图复核。
- `V0.6b 覆盖` 指当前路线图计划的 `learned_skill` / `invention_idea` / `self_portrait` / `generic_narrative` 四个模板是否能提供合适脚手架，不是指 AI 是否能勉强生成内容。

---

## 核心结论

1. **现有 8 个 TopicType 不能覆盖 3-6 年级课内同步作文。** 严格按当前枚举含义计算，只能覆盖约 16/57, 即 28%。如果只看 V0.6b 计划的 3 个模板加兜底，严格覆盖约 12/57, 即 21%。
2. **四下 7 篇不是完整代表样本。** 四下确实暴露了固定叙事模板的问题，但 3-6 年级还高频出现说明介绍类、读后感/推荐类、应用文类、中心意思/观点表达类、观察记录类。
3. **最高频的写作模式不是单一叙事。** 按 writing mode 聚合：叙事 11、实用/说明 10、想象 10、写人 7、感想/推荐 6、动物/物品观察 5、故事改写/概括 4、写景/游记 4。
4. **V0.6c 原计划补的 4 个模板不够。** `my_paradise` / `travel_writing` / `story_rewrite` / `animal_friend` 能补齐四下样本，但对 3-6 年级整体只能把严格覆盖从约 21% 提高到约 28%。即使把这些模板泛化，仍会遗漏说明介绍、应用文、读后感/推荐、中心意思表达等核心题型。
5. **V0.6b 应避免把某个教材题目直接固化成一个窄枚举。** `self_portrait` 应升级为 `person_portrait`；`invention_idea` 应属于更大的想象/创意设定族；`animal_friend` 应升级为动物/植物/物品观察族。

---

## Full Taxonomy Table

| 年级 | 册 | 单元 | 原题 | 提示摘要 | likely topic_type | 内容来源 | writing mode | 推荐模板 | 素材卡 slots | 提纲形状 | V0.6b 覆盖 | 需新 TopicType |
|---:|---|---:|---|---|---|---|---|---|---|---|---|---|
| 3 | 上 | 1 | 猜猜他是谁 | 选一个同学，写几处特点，让别人猜出是谁。 | `person_portrait` | observation | person_portrait | 写人特点模板 | 外貌线索 / 性格动作 / 典型事例 / 不暴露姓名的提示 | 不说姓名 -> 特点一 -> 特点二 -> 典型小事 -> 猜一猜 | 部分，需把 `self_portrait` 泛化 | 是，`person_portrait` |
| 3 | 上 | 2 | 写日记 | 记录一天生活中的事，注意日记格式。 | `practical_writing` | real_experience | practical/expository | 日记模板 | 日期星期天气 / 今天的事 / 过程或发现 / 心情想法 | 日期格式 -> 事情发生 -> 经过/发现 -> 心情 | 否 | 是，`practical_writing` |
| 3 | 上 | 3 | 续写故事 | 根据图中人物和已有情境，把后续故事写完整。 | `story_continuation` | topic_requirement + imagined_setting | story rewrite | 续写故事模板 | 已有情境 / 人物愿望 / 接下来发生 / 结局 | 原情境 -> 新困难 -> 行动 -> 结局 | 否，V0.6c `story_rewrite` 也只部分适配 | 是，或扩展 `story_rewrite` |
| 3 | 上 | 4 | 我来编童话 | 从词语组合中选择角色、时间、地点，编童话。 | `imaginative_story` | imagined_setting | imagination | 想象故事模板 | 角色 / 场景 / 魔法或变化 / 困难 / 结局 | 角色出场 -> 奇妙设定 -> 遇到问题 -> 解决 -> 结尾 | 否 | 是，`imaginative_story` |
| 3 | 上 | 5 | 我们眼中的缤纷世界 | 写最近观察印象最深的事物和发现。 | `observation_log` | observation | animal/object observation | 观察记录模板 | 观察对象 / 样子变化 / 多感官细节 / 新发现 | 观察什么 -> 怎么观察 -> 发现变化 -> 感受 | 否 | 是，`observation_log` |
| 3 | 上 | 6 | 这儿真美 | 介绍身边一处美景，围绕一个意思写一段话。 | `scene_description` | observation | travel/scenery | 景物描写模板 | 地点 / 景物顺序 / 颜色声音气味 / 最美处 | 总写这儿真美 -> 分景物描写 -> 最美画面 -> 感受 | 否，`travel_writing` 部分适配 | 是，或扩展 `place_scenery` |
| 3 | 上 | 7 | 我有一个想法 | 写生活中需要改进的问题，提出想法或建议。 | `problem_solution` | child_confirmed | practical/expository | 问题建议模板 | 发现的问题 / 为什么影响人 / 我的建议 / 可能效果 | 问题 -> 原因/影响 -> 建议 -> 期待 | 否 | 是，`problem_solution` |
| 3 | 上 | 8 | 那次经历真难忘 | 回忆一次难忘经历，写清经过和心情。 | `generic_narrative` | real_experience | narrative | 经历叙事模板 | 事件 / 关键经过 / 心情变化 / 难忘原因 | 起因 -> 经过 -> 结果 -> 感受 | 是 | 否 |
| 3 | 下 | 1 | 我的植物朋友 | 观察一种植物，借助记录卡写清样子和感受。 | `animal_object_observation` | observation | animal/object observation | 植物观察模板 | 名称 / 样子颜色气味 / 生长变化 / 我喜欢它的原因 | 介绍植物 -> 细写样子 -> 变化或发现 -> 感受 | 否 | 是，泛化 `animal_friend` |
| 3 | 下 | 2 | 看图画，写一写 | 观察图画中的人物、动作和可能的话，介绍画面内容。 | `picture_prompt_story` | topic_requirement | narrative | 看图作文模板 | 图中人物 / 动作 / 可能的话 / 画面顺序 | 图上有什么 -> 人物在做什么 -> 发生了什么 -> 感受 | 否 | 是，`picture_prompt_story` |
| 3 | 下 | 4 | 我做了一项小实验 | 介绍自己做过的小实验，写清过程和发现。 | `experiment_process` | observation + real_experience | practical/expository | 实验过程模板 | 实验名称 / 准备材料 / 步骤 / 结果发现 / 心情 | 目的 -> 准备 -> 步骤 -> 结果 -> 发现 | 否 | 是，可归入 `expository_introduction` |
| 3 | 下 | 5 | 奇妙的想象 | 选择或自拟想象题，写一个大胆想象的故事。 | `imaginative_story` | imagined_setting | imagination | 想象故事模板 | 主角 / 奇妙设定 / 变化 / 冲突 / 结局 | 设定 -> 奇妙事件 -> 困难 -> 解决 -> 结尾 | 否 | 是，`imaginative_story` |
| 3 | 下 | 6 | 身边那些有特点的人 | 选一个身边有特点的人，用事例表现特点。 | `person_portrait` | observation + real_experience | person_portrait | 写人特点模板 | 人物 / 特点词 / 典型事例 / 评价 | 人物印象 -> 特点 -> 事例 -> 总结 | 部分，需泛化 `self_portrait` | 是，`person_portrait` |
| 3 | 下 | 7 | 国宝大熊猫 | 围绕问题和资料，介绍大熊猫。 | `expository_introduction` | topic_requirement | practical/expository | 说明介绍模板 | 资料来源 / 类别外形 / 食物栖息地 / 为什么是国宝 | 提出对象 -> 分方面介绍 -> 补充有趣信息 -> 总结 | 否 | 是，`expository_introduction` |
| 3 | 下 | 8 | 这样想象真有趣 | 让动物失去或改变特征，编有趣故事。 | `imaginative_story` | imagined_setting | imagination | 想象故事模板 | 动物主角 / 特征变化 / 生活变化 / 奇异事件 / 结局 | 变化发生 -> 新麻烦 -> 尝试 -> 结果 -> 趣味结尾 | 否 | 是，`imaginative_story` |
| 4 | 上 | 1 | 推荐一个好地方 | 推荐喜欢的地方，写清位置、特点和推荐理由。 | `place_recommendation` | real_experience | reflection/recommendation | 地点推荐模板 | 地点 / 特别之处 / 推荐理由 / 适合谁去 | 地点是什么 -> 有什么好 -> 为什么推荐 -> 邀请 | 否，`my_paradise`/`travel_writing` 部分适配 | 是，或扩展 `place_scenery` |
| 4 | 上 | 2 | 我的家人 | 选择家人或几位家人，写出最与众不同的特点。 | `person_portrait` | real_experience | person_portrait | 写人特点模板 | 家人 / 外貌或性格 / 典型事例 / 我的感情 | 人物印象 -> 特点 -> 事例 -> 感情 | 部分，需泛化 `self_portrait` | 是，`person_portrait` |
| 4 | 上 | 3 | 写观察日记 | 连续观察对象，用日记记录变化和想法。 | `observation_log` | observation | animal/object observation | 观察日记模板 | 观察对象 / 日期变化 / 过程记录 / 想法 | 日期记录 -> 变化一 -> 变化二 -> 发现 | 否 | 是，`observation_log` |
| 4 | 上 | 4 | 我和____过一天 | 想象与故事人物过一天，会去哪、做什么、发生什么。 | `imaginative_story` | imagined_setting + reading_based | imagination | 想象同游模板 | 选择人物 / 一天场景 / 一起做的事 / 意外 / 收获 | 遇见人物 -> 一起行动 -> 发生故事 -> 分别/收获 | 否 | 是，`imaginative_story` |
| 4 | 上 | 5 | 生活万花筒 | 选印象深的一件事，按顺序写清起因经过结果。 | `generic_narrative` | real_experience | narrative | 经历叙事模板 | 事情 / 起因 / 经过 / 结果 / 感受 | 起因 -> 经过 -> 结果 -> 感受 | 是 | 否 |
| 4 | 上 | 6 | 记一次游戏 | 写一次游戏，写清准备、过程、印象深处和感受。 | `generic_narrative` | real_experience | narrative | 活动叙事模板 | 游戏规则 / 游戏过程 / 重点动作 / 感受 | 游戏前 -> 游戏中 -> 高潮 -> 结束感受 | 是 | 否 |
| 4 | 上 | 7 | 写信 | 给亲友或他人写信，注意称呼、问候、正文、祝福、署名日期。 | `practical_writing` | child_confirmed | practical/expository | 书信模板 | 收信人 / 想说的事 / 语气情感 / 格式 | 称呼问候 -> 正文几件事 -> 祝福 -> 署名日期 | 否 | 是，`practical_writing` |
| 4 | 上 | 8 | 我的心儿怦怦跳 | 选一件让心跳加快的事，写清过程和当时感受。 | `generic_narrative` | real_experience | narrative | 情绪叙事模板 | 事件 / 心跳时刻 / 身体反应 / 情绪变化 | 事情开始 -> 紧张/激动升级 -> 结果 -> 回看感受 | 是，兜底可用 | 否 |
| 4 | 下 | 1 | 我的乐园 | 介绍让自己快乐的地方，以及在那里做什么、为什么快乐。 | `my_paradise` | real_experience | travel/scenery | 乐园地点模板 | 地点样子 / 在这里做什么 / 最快乐时刻 / 为什么是乐园 | 这是什么地方 -> 长什么样 -> 我做什么 -> 为什么快乐 | 否，当前 V0.6b 不含此模板 | 否，已有但建议并入 `place_scenery` |
| 4 | 下 | 2 | 我的奇思妙想 | 写一种想发明的神奇东西，介绍样子、功能和用处。 | `invention_idea` | imagined_setting | imagination | 发明设想模板 | 发明名称 / 样子结构 / 功能 / 用处 / 为什么想发明 | 发明什么 -> 长什么样 -> 功能 -> 帮助谁 -> 期待 | 是 | 否，但可并入想象创意族 |
| 4 | 下 | 4 | 我的动物朋友 | 在某个情境中向别人介绍动物朋友的特点。 | `animal_friend` | real_experience + imagined_setting | animal/object observation | 动物朋友模板 | 介绍情境 / 外形 / 习性 / 我和它的故事 / 感情 | 情境 -> 外形 -> 习性 -> 一件事 -> 感情 | 否，V0.6c 才计划 | 否，已有但建议泛化 |
| 4 | 下 | 5 | 游____ | 写游览过的地方，按游览顺序介绍重点景物。 | `travel_writing` | real_experience | travel/scenery | 游记模板 | 游览路线 / 重点景物 / 细节描写 / 游览感受 | 去哪 -> 先到哪 -> 重点景物 -> 后到哪 -> 感受 | 否，V0.6c 才计划 | 否，已有 |
| 4 | 下 | 6 | 我学会了____ | 写学会一件事的过程、困难、克服方法和心情。 | `learned_skill` | real_experience | narrative | 学会过程模板 | 学什么 / 困难 / 关键动作 / 学会后心情 | 为什么学 -> 怎么学 -> 困难克服 -> 学会 -> 感受 | 是 | 否 |
| 4 | 下 | 7 | 我的“自画像” | 向新班主任介绍自己，写外貌、性格、爱好和事例。 | `self_portrait` | child_confirmed | person_portrait | 自我画像模板 | 外貌 / 性格 / 爱好特长 / 典型事例 | 我是谁 -> 外貌 -> 性格事例 -> 爱好 -> 这就是我 | 是 | 否，但建议改为 `person_portrait` |
| 4 | 下 | 8 | 故事新编 | 选择熟悉故事，改变结局或关键情节，创编新故事。 | `story_rewrite` | reading_based + imagined_setting | story rewrite | 故事改编模板 | 原故事 / 保留元素 / 改变点 / 新情节 / 新结局 | 原故事 -> 从哪改变 -> 新情节 -> 新结局 -> 新意思 | 否，V0.6c 才计划 | 否，已有 |
| 5 | 上 | 1 | 我的心爱之物 | 写一件心爱之物的样子、来历和喜爱之情。 | `beloved_object` | real_experience | animal/object observation | 心爱之物模板 | 物品样子 / 来历 / 特别之处 / 情感故事 | 它是什么 -> 样子 -> 来历/故事 -> 为什么心爱 | 否 | 是，可归入 `animal_object_observation` |
| 5 | 上 | 2 | “漫画”老师 | 用文字给老师画漫画，抓住外貌、性格、喜好和事例。 | `person_portrait` | observation + real_experience | person_portrait | 写人特点模板 | 老师特点 / 外貌动作 / 口头禅或习惯 / 典型事例 | 漫画式印象 -> 特点一 -> 事例 -> 评价 | 部分，需泛化 `self_portrait` | 是，`person_portrait` |
| 5 | 上 | 3 | 缩写故事 | 把较长故事缩写成简短故事，保留主要内容。 | `story_summary` | reading_based | story rewrite | 故事缩写模板 | 原故事主干 / 必留人物事件 / 可删细节 / 连贯语句 | 读懂原文 -> 抓主干 -> 合并删减 -> 连贯成文 | 否 | 是，`story_summary` |
| 5 | 上 | 4 | 二十年后的家乡 | 想象二十年后的家乡变化，按提纲分段写。 | `future_imagination` | imagined_setting | imagination | 未来想象模板 | 未来时间 / 环境变化 / 工作生活变化 / 回乡场景 / 情感 | 穿越回乡 -> 几方面变化 -> 重点场景 -> 向往 | 否 | 是，可归入 `imaginative_story` |
| 5 | 上 | 5 | 介绍一种事物 | 选择了解或感兴趣的事物，搜集资料，分方面介绍。 | `expository_introduction` | topic_requirement | practical/expository | 说明介绍模板 | 对象 / 主要特点 / 分方面资料 / 说明方法 / 来源 | 对象总介 -> 方面一 -> 方面二 -> 方面三 -> 总结 | 否 | 是，`expository_introduction` |
| 5 | 上 | 6 | 我想对您说 | 选择倾诉对象，把心里话写成一封信。 | `practical_writing` | child_confirmed | practical/expository | 书信倾诉模板 | 倾诉对象 / 想说的事 / 真实感受 / 希望或建议 / 格式 | 称呼 -> 为什么想说 -> 几件心里话 -> 期待 -> 署名 | 否 | 是，`practical_writing` |
| 5 | 上 | 7 | ____即景 | 观察自然景观或现象，写出景物变化。 | `scene_description` | observation | travel/scenery | 即景描写模板 | 观察对象 / 时间或空间顺序 / 动态变化 / 画面细节 | 看到什么 -> 顺序展开 -> 动态变化 -> 感受 | 否，`travel_writing` 部分适配 | 是，或扩展 `place_scenery` |
| 5 | 上 | 8 | 推荐一本书 | 向同学推荐读过的好书，写清基本信息和推荐理由。 | `book_recommendation` | reading_based | reflection/recommendation | 图书推荐模板 | 书名作者 / 内容简介 / 推荐理由 / 精彩处 / 适合读者 | 书的基本信息 -> 主要内容 -> 推荐理由 -> 邀请阅读 | 否 | 是，归入 `reading_response_recommendation` |
| 5 | 下 | 1 | 那一刻，我长大了 | 写成长过程中印象最深的一刻和真实感受。 | `generic_narrative` | real_experience | narrative | 成长叙事模板 | 成长时刻 / 前因 / 关键细节 / 内心变化 | 事情背景 -> 那一刻 -> 我的变化 -> 现在回看 | 是，兜底可用 | 否 |
| 5 | 下 | 2 | 写读后感 | 写读一篇文章或一本书后的感想，联系阅读积累和生活经验。 | `reading_response` | reading_based | reflection/recommendation | 读后感模板 | 作品内容 / 印象最深处 / 我的感受 / 生活联系 | 介绍作品 -> 触动点 -> 感想 -> 联系自己 -> 总结 | 否 | 是，`reading_response_recommendation` |
| 5 | 下 | 4 | 他____了 | 写一个人生气、陶醉、伤心等样子，表现人物内心。 | `person_portrait` | observation + real_experience | person_portrait | 人物状态描写模板 | 人物 / 情绪状态 / 表情动作语言 / 内心推测 / 前因后果 | 他怎么了 -> 表现细节 -> 前因后果 -> 反映内心 | 部分，需泛化 `self_portrait` | 是，`person_portrait` |
| 5 | 下 | 5 | 形形色色的人 | 选择一个人，用典型事例具体表现人物特点。 | `person_portrait` | observation + real_experience | person_portrait | 写人特点模板 | 人物 / 核心特点 / 典型事例 / 细节描写 / 评价 | 人物印象 -> 典型事例 -> 细节 -> 总结特点 | 部分，需泛化 `self_portrait` | 是，`person_portrait` |
| 5 | 下 | 6 | 神奇的探险之旅 | 选择人物、场景、装备、险情，编探险故事。 | `adventure_imagination` | imagined_setting | imagination | 探险故事模板 | 探险队 / 目的地 / 装备 / 险情 / 求生办法 | 出发 -> 遇险 -> 合作解决 -> 新发现 -> 归来 | 否 | 是，可归入 `imaginative_story` |
| 5 | 下 | 7 | 中国的世界文化遗产 | 选择一处文化遗产，搜集整理资料后介绍。 | `expository_introduction` | topic_requirement + reading_based | practical/expository | 资料说明模板 | 遗产名称 / 历史背景 / 现状特点 / 资料来源 / 价值 | 对象总介 -> 历史 -> 特点 -> 价值 -> 来源 | 否 | 是，`expository_introduction` |
| 5 | 下 | 8 | 漫画的启示 | 观察漫画内容，写清获得的启示和思考。 | `visual_reflection` | topic_requirement | reflection/recommendation | 漫画启示模板 | 漫画内容 / 讽刺或启示 / 联系生活 / 我的看法 | 看到了什么 -> 想到什么 -> 生活例子 -> 启示 | 否 | 是，`visual_reflection` 或归入 `central_idea_reflection` |
| 6 | 上 | 1 | 变形记 | 想象自己变成另一种事物后经历的世界。 | `imaginative_story` | imagined_setting | imagination | 变形想象模板 | 变成什么 / 新视角 / 新困难 / 奇遇 / 发现 | 变形 -> 新世界 -> 遭遇 -> 体验 -> 回看 | 否 | 是，`imaginative_story` |
| 6 | 上 | 2 | 多彩的活动 | 选一次活动，写清活动过程、重点场面和体会。 | `generic_narrative` | real_experience | narrative | 活动叙事模板 | 活动名称 / 场面 / 重点人物动作 / 体会 | 活动前 -> 活动中 -> 重点场面 -> 体会 | 是，兜底可用 | 否 |
| 6 | 上 | 3 | ____让生活更美好 | 选一个话题，写它怎样影响生活并说明原因。 | `central_idea_reflection` | child_confirmed | reflection/recommendation | 主题表达模板 | 话题 / 为什么更美好 / 生活例子 / 我的观点 | 提出观点 -> 例子一 -> 例子二 -> 总结提升 | 否 | 是，`central_idea_reflection` |
| 6 | 上 | 4 | 笔尖流出的故事 | 根据环境和人物设定，创编情节曲折的虚构故事。 | `imaginative_story` | topic_requirement + imagined_setting | imagination | 虚构故事模板 | 环境 / 人物 / 目标或冲突 / 情节转折 / 结局 | 环境人物 -> 冲突 -> 转折 -> 高潮 -> 结局 | 否 | 是，`imaginative_story` |
| 6 | 上 | 5 | 围绕中心意思写 | 选择一个字或中心意思，从不同方面或事例表达。 | `central_idea_reflection` | child_confirmed | reflection/recommendation | 中心意思模板 | 中心词 / 方面一 / 方面二 / 典型事例 / 点题句 | 中心意思 -> 多方面展开 -> 重点事例 -> 回扣中心 | 否 | 是，`central_idea_reflection` |
| 6 | 上 | 6 | 学写倡议书 | 针对想法或问题，写一份倡议书争取大家支持。 | `practical_writing` | topic_requirement | practical/expository | 倡议书模板 | 倡议对象 / 问题背景 / 倡议内容 / 具体做法 / 署名日期 | 标题称呼 -> 背景理由 -> 倡议事项 -> 号召 -> 署名日期 | 否 | 是，`practical_writing` |
| 6 | 上 | 7 | 我的拿手好戏 | 写自己的拿手本领，突出重点部分和趣事。 | `learned_skill` | real_experience | narrative | 拿手本领模板 | 拿手好戏 / 怎么练成 / 重点展示 / 趣事 / 得意感 | 点明本领 -> 练成过程 -> 重点展示 -> 收获 | 是，`learned_skill` 可扩展 | 否 |
| 6 | 上 | 8 | 有你，真好 | 写想到的某个人，以及让自己触动的事和真挚情感。 | `generic_narrative` | child_confirmed + real_experience | narrative | 感情叙事模板 | 这个你是谁 / 触动事件 / 细节 / 真情表达 | 想到你 -> 一件事 -> 细节感受 -> 真好 | 是，兜底可用 | 否 |
| 6 | 下 | 1 | 家乡的风俗 | 介绍一种家乡风俗，或写参与风俗活动的经历。 | `culture_introduction` | real_experience + reading_based | practical/expository | 风俗介绍模板 | 风俗名称 / 来历特点 / 活动过程 / 我的体验 / 看法 | 风俗是什么 -> 怎么做 -> 重点场景 -> 我的体验/看法 | 否 | 是，可归入 `expository_introduction` |
| 6 | 下 | 2 | 写作品梗概 | 对书的内容进行概括，用简练语言介绍主要内容。 | `story_summary` | reading_based | story rewrite | 作品梗概模板 | 作品 / 主线人物 / 主要情节 / 保留要点 / 连贯过渡 | 读懂主线 -> 筛选概括 -> 合并成段 -> 语言连贯 | 否 | 是，`story_summary` |
| 6 | 下 | 3 | 让真情自然流露 | 选择印象深的感受，回顾事情经过，真实自然表达情感变化。 | `generic_narrative` | real_experience | narrative | 情感叙事模板 | 情感词 / 事情经过 / 情感变化 / 具体细节 | 事情背景 -> 情感产生 -> 变化过程 -> 自然流露 | 是，兜底可用 | 否 |
| 6 | 下 | 5 | 插上科学的翅膀飞 | 写科幻故事，把不可思议的科学技术带入人物生活。 | `science_imagination` | imagined_setting + topic_requirement | imagination | 科幻想象模板 | 科技设定 / 生活环境 / 人物目标 / 科技影响 / 结局 | 科技设定 -> 人物生活 -> 冲突或任务 -> 影响 -> 结尾 | 否 | 是，可归入 `imaginative_story` |

---

## TopicType Coverage Summary

### 按 writing mode 聚合

| writing mode | 数量 | 占比 | 代表题目 |
|---|---:|---:|---|
| narrative | 11 | 19% | 那次经历真难忘、生活万花筒、记一次游戏、那一刻我长大了、多彩的活动、有你真好 |
| practical/expository | 10 | 18% | 写日记、国宝大熊猫、介绍一种事物、我想对您说、学写倡议书、中国的世界文化遗产 |
| imagination | 10 | 18% | 我来编童话、奇妙的想象、我和____过一天、变形记、笔尖流出的故事、插上科学的翅膀飞 |
| person_portrait | 7 | 12% | 猜猜他是谁、我的家人、“漫画”老师、他____了、形形色色的人、我的“自画像” |
| reflection/recommendation | 6 | 11% | 推荐一个好地方、推荐一本书、写读后感、漫画的启示、围绕中心意思写 |
| animal/object observation | 5 | 9% | 我的植物朋友、我的动物朋友、我的心爱之物、写观察日记 |
| story rewrite | 4 | 7% | 续写故事、故事新编、缩写故事、写作品梗概 |
| travel/scenery | 4 | 7% | 这儿真美、我的乐园、游____、____即景 |

### 当前 TopicType 覆盖判断

| 口径 | 覆盖数 | 覆盖率 | 说明 |
|---|---:|---:|---|
| 当前 8 个 TopicType 严格匹配 | 16/57 | 28% | 四下 7 篇全在枚举内，但 3-6 年级整体大量缺口。 |
| V0.6b 计划 3 模板，不含兜底 | 4/57 | 7% | `learned_skill` 2、`invention_idea` 1、`self_portrait` 1。 |
| V0.6b 计划 3 模板 + `generic_narrative` | 12/57 | 21% | 主要靠兜底覆盖叙事，非叙事仍大面积缺失。 |
| 若把 `self_portrait` 泛化为 `person_portrait` | 18/57 | 32% | 立即多覆盖 6 个写人题，ROI 很高。 |
| V0.6b + 原 V0.6c 4 模板严格匹配 | 16/57 | 28% | 只比 V0.6b 多 4 个严格命中的题。 |
| 若 V0.6c 4 模板泛化为地点/观察/故事族 | 约 30/57 | 约 53% | 仍缺说明介绍、应用文、读后感/推荐、中心意思表达。 |

---

## Recommended Changes To V0.6b TopicType Enum

### 1. 不建议把教材题名直接变成窄枚举

四下推导出的 `my_paradise`、`animal_friend`、`self_portrait` 很适合验证四下，但对 3-6 年级会过窄。建议改成“题型族 + variant”的设计：

```python
class TopicType(str, Enum):
    GENERIC_NARRATIVE = "generic_narrative"
    LEARNED_SKILL = "learned_skill"

    # Rename/replace self_portrait. subject can be self / family / teacher / classmate / other.
    PERSON_PORTRAIT = "person_portrait"

    # Covers my_paradise, travel_writing, scene_description, place_recommendation.
    PLACE_SCENERY = "place_scenery"

    # Covers animal_friend, plant_friend, beloved_object, observation diary.
    ANIMAL_OBJECT_OBSERVATION = "animal_object_observation"

    # Covers fairy tale, fantasy day, adventure, future home, transformation, sci-fi.
    IMAGINATIVE_STORY = "imaginative_story"

    # Keep as a distinct scaffold variant if the invention structure needs explain-by-function cards.
    INVENTION_IDEA = "invention_idea"

    # Covers continuation and rewrite. Summary is related but should be a separate template.
    STORY_ADAPTATION = "story_adaptation"
    STORY_SUMMARY = "story_summary"

    EXPOSITORY_INTRODUCTION = "expository_introduction"
    PRACTICAL_WRITING = "practical_writing"
    READING_RESPONSE_RECOMMENDATION = "reading_response_recommendation"
    CENTRAL_IDEA_REFLECTION = "central_idea_reflection"
    PICTURE_PROMPT_STORY = "picture_prompt_story"
```

### 2. V0.6b 最小修改建议

如果 V0.6b 仍限制为 3 个模板 + 兜底，建议调整为：

| V0.6b 模板 | 覆盖目标 | 原路线图对应关系 |
|---|---|---|
| `generic_narrative` | 经历、活动、成长、情绪叙事；`learned_skill` 作为 variant | 保留兜底，`learned_skill` 不必单独 P0 |
| `person_portrait` | 自画像、家人、老师、同学、形形色色的人 | 替代窄 `self_portrait` |
| `imaginative_story` | 童话、变形、探险、科幻、未来、与人物过一天；`invention_idea` 作为 design variant | 泛化窄 `invention_idea` |
| `expository_introduction` | 国宝大熊猫、介绍一种事物、文化遗产、家乡风俗、小实验 | 新增，弥补路线图未覆盖的高频说明介绍类 |

这个组合的实际覆盖可达约 30-32/57，即 53-56%，远高于当前路线图的 21-32%。

---

## Recommended Template Priority

### V0.6b - 题型适配 v1

P0:
- `generic_narrative` 强化为“经历/活动/成长/情绪”通用叙事模板，并把 `learned_skill` 作为预设 variant。
- `person_portrait` 替代 `self_portrait`，支持 self / other 的人物对象。
- `imaginative_story` 覆盖想象故事高频族，保留 `invention_idea` 的“样子/功能/用处”素材卡作为 variant。
- `expository_introduction` 覆盖说明介绍和资料整理类，这是四下样本没有充分暴露、但 3-6 年级高频出现的新风险。

P1:
- 题型手动选择 + AI 建议识别。
- `content_source_type` 明确进入 template selection，不再只区分“真实经历 vs 想象”。

### V0.6c - 扩展高频题型族

P0:
- `place_scenery`: 合并 `my_paradise`、`travel_writing`、`scene_description`、`place_recommendation`，用 variant 控制“地点推荐/乐园/游记/即景”。
- `animal_object_observation`: 泛化 `animal_friend`，覆盖植物、动物、物品、观察日记。
- `practical_writing`: 日记、书信、倡议书、倾诉信等格式类写作。
- `story_adaptation` + `story_summary`: 如果只能做一个，先做 `story_adaptation` 以补四下《故事新编》；但五上/六下的缩写和梗概需要 `story_summary`，不能长期靠改写模板。

P1:
- `reading_response_recommendation`: 推荐一本书、写读后感、漫画的启示。
- `central_idea_reflection`: 围绕中心意思写、____让生活更美好、我有一个想法。

### V0.7 - 难度与表达目标分化

- 为 `reading_response_recommendation` 拆分“读后感 / 图书推荐 / 漫画启示”。
- 为 `central_idea_reflection` 增加观点表达、例证组织和中心句回扣。
- 为 `expository_introduction` 增加资料来源、引用、表格/图片辅助信息的校验。
- 对 3-4 年级和 5-6 年级使用不同追问深度：低年级偏“写清楚”，高年级偏“结构、重点、表达效果”。

---

## Risks If V0.6b Only Ships learned_skill / invention_idea / self_portrait / generic_narrative

1. **覆盖率低于产品定位。** 严格覆盖约 12/57, 即 21%。即使把 `self_portrait` 临时泛化成所有写人，也只有约 18/57, 即 32%。
2. **高频新题型继续无脚手架。** 说明介绍类、应用文类、读后感/推荐类、中心意思表达类都无法得到合适素材卡和提纲。
3. **兜底模板会被滥用。** 大量题会回到“起因/经过/结果/感受”，孩子仍会感到“题目问的不是这个”。
4. **四下优化不能代表 3-6 年级。** 四下 7 篇确实证明需要模板化，但它低估了说明、应用、阅读回应和主题表达的比例。
5. **AI 不替孩子决定内容的原则仍不完整。** 说明介绍和读后感类需要处理 `reading_based` 和 `topic_requirement`，不是只让孩子确认真实经历或想象设定。
6. **后续 AI 出题会受限。** 如果 TopicType 仍按窄题名设计，AI 题目推荐很容易生成无法落入 scaffold 的题。

---

## Source Gap To Resolve

六下截图集中未收录可能存在的《心愿》。如果补入该题，预计会归入 `central_idea_reflection` 或 `practical_writing` 的 personal-wish variant，不会被当前 V0.6b 三模板覆盖。因此补图大概率会进一步强化“需要中心意思/愿望表达模板”的结论，而不会改变主结论。
