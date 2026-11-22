# 通用 AI 剪辑 Skill 对照与取舍

2026-11-22。我按剪一条片真正要作的决定来比较：看哪份原件、哪句话值得留、这一秒为什么切、哪个画面能说明台词、改完如何看出差别。七套主查项目覆盖这些环节。判断依据是能读到的规则、实现、案例与测试；公开样例的存在和本机实际跑通分别记录。

## 七套主查项目，以及我们具体学什么

| 上游与我读的部分 | 别人怎样作决定、留下什么 | 对照我们原来的做法，本次怎样用 |
| --- | --- | --- |
| **Ethan Woo · video-editing**。拆参考片、逐句选 B-roll、剪辑总流程。[参考片分析](https://github.com/gitethanwoo/video-editing/blob/8b633c2d698410e523f95335aa6433766264cc7f/skills/analyze-video-editing/SKILL.md) · [选镜方法](https://github.com/gitethanwoo/video-editing/blob/8b633c2d698410e523f95335aa6433766264cc7f/skills/find-broll/SKILL.md) | 以真实参考片为输入，先定位剪点、文字和声音，再看关键段的连续帧，最后解释这一剪承担的叙事作用。分开写时间测量、画面观察和原因推断。选 B-roll 时写它要承接的话以及能说明的具体内容。 | 原来有逐句分镜和锚词。这次加上参考片的三层记录。比如可以测到首页出现多久，看见阿桂让位；“让观众先看成果”属于剪辑判断。上游说明已按固定版本收入库中。 |
| **Chengfeng · 中文口播剪辑**。对照本机 0.10.8 的剪口播、加画面规则，以及上游发布快照的判例。[删句判例](https://github.com/Agentchengfeng/chengfeng-videocut-skills/blob/a33b43e08c34fa8beeb5e78498e852f4e80975a5/plugins/chengfeng-videocut/skills/chengfeng-cut/references/semantic-deletion.md) · [滚动时的标注](https://github.com/Agentchengfeng/chengfeng-videocut-skills/blob/a33b43e08c34fa8beeb5e78498e852f4e80975a5/plugins/chengfeng-videocut/skills/chengfeng-visual/references/visual-judgment.md) | 按播放顺序判断残句、改口和整句重录；把几次重说排在一起读，发现后一句新加的条件。做固定框之前抽帧定位屏幕停稳和下一次操作，框在页面移动前撤走。 | 原有粗剪能给候选删段，整句重录的语义要靠编辑再判。现在把各遍新增信息、专名依据和拼接后的念法写入有歧义的行；框选绑定稳定的页面状态。上游给的提前 0.2 秒是调时参考；当期页面、帧率与动作决定实际出点。沿用已有本地转写和工程。 |
| **Melvynx · video-agent-skills**。素材库、长访谈选段、短片场景和音乐参考。[素材库](https://github.com/Melvynx/video-agent-skills/blob/f4542923f7f796a1fa0e544cbfc1109d5eec87d8/skills/broll/SKILL.md) · [访谈选段](https://github.com/Melvynx/video-agent-skills/blob/f4542923f7f796a1fa0e544cbfc1109d5eec87d8/skills/clips/SKILL.md) | 给已有素材打可检索的动作标签，登记使用和退回；从长稿里找故事转折、明确主张或有答案的问题，单独播放时检查开头指代和结尾收束。项目还把某首乐在人声下被退回的原因记到用乐说明里。 | 我们已有动作、出处和使用集数。现在也记“为什么退、在哪种用途退”。同一个校门镜头能交代地点，不能说明绩点。采访想切成短片时，给源时码、首尾原话和上下文；作者自己的配乐表、固定版面和时长留在对应栏目。 |
| **ranahaani · i-hate-editing**。实物证据、人物构图、声音规则、几何测试和人脸安全区实现。[证据镜头](https://github.com/ranahaani/i-hate-editing/blob/a5add74b595f652e0da9577bbf8f6fc4b1d57457/rules/proof.md) · [取景比较](https://github.com/ranahaani/i-hate-editing/blob/a5add74b595f652e0da9577bbf8f6fc4b1d57457/rules/framing.md) · [安全区实现](https://github.com/ranahaani/i-hate-editing/blob/a5add74b595f652e0da9577bbf8f6fc4b1d57457/scripts/safe_zone.py) | 说到某件作品或数字就展示原物；对有争议的人物站位，从同一真实帧试多个裁切，再看眼睛、文字和主体是否撞在一起。源码的自动选区按 1080×1920 竖屏和脸框计算。 | 我们已要求 UI 真实、圆框让位，但“让位”缺少对照办法。现在拿同帧比较独占与小窗布局，小窗要带来可指出的新信息。竖屏的固定比例不适用于校园横屏；脸框也识别不了需要保护的按钮、姓名栏或学号。声音保留按动作落点、同音量比较的办法，按实际台词选密度。 |
| **WhiteTowerAI · cut-as-code**。粗剪、B-roll 计划、修改后对照。[剪辑技能](https://github.com/WhiteTowerAI/cut-as-code/blob/a96c13e6eaa72e6882e78df08ee4c04fa7be3bc4/skills/video-cut/SKILL.md) · [B-roll 的时间依据](https://github.com/WhiteTowerAI/cut-as-code/blob/a96c13e6eaa72e6882e78df08ee4c04fa7be3bc4/skills/video-add-b-roll/SKILL.md) · [版本对照](https://github.com/WhiteTowerAI/cut-as-code/blob/a96c13e6eaa72e6882e78df08ee4c04fa7be3bc4/skills/video-edit-compare/SKILL.md) | 素材选择关联当前剪辑版、逐词稿和成片时间；用剪后画面判断插入素材会不会遮挡。在较早步骤调整剪点后，重新核对依赖这些时码的轨道。 | 我们原有源入出点、成片时间和字幕检查，缺少删剪后两者的实际换算。现在用[字幕映射](../scripts/map_cues.py)重算；整句丢失、截断、跨剪点都能定位到原句。画面或音效跟随对应词复核，已经获准的同一份下载沿用原许可范围。 |
| **Browser Use · video-use**。总技能和按区间取样的实际脚本。[编辑入口](https://github.com/browser-use/video-use/blob/43cfc566833548093455c9d4a46bd69913b7e552/SKILL.md) · [审片源码](https://github.com/browser-use/video-use/blob/43cfc566833548093455c9d4a46bd69913b7e552/helpers/timeline_view.py) | 对犹豫的停顿或争议剪点，给视频、时间范围和可选逐词稿；输出同一段的等间隔画面、波形与词。可以直观看清台词到哪了、屏幕正在放什么，再决定是否切。 | 以前能验证视频解码、字幕起止和声音版画面一致。现在用[本地审片入口](../scripts/review_window.py)把问题聚焦到一句，已在三段本机成片跑通。使用原作者 MIT 脚本，接入 Windows 中文字体和已有逐词数据，区间审片无需转写账号。 |
| **MakeMyClip · editor**。技能入口、会话快照与剪辑软件交接能力。[操作说明与依赖](https://github.com/MakeMyClip/editor/blob/e090b420f2f0c2c5fd4b16d3b741348fdd6d8671/SKILL.md) · [快照实现](https://github.com/MakeMyClip/editor/blob/e090b420f2f0c2c5fd4b16d3b741348fdd6d8671/src/tools/snapshot.ts) | 把剪辑操作存进会话，按操作数或名称保存快照，便于试另一版后撤回。上游还提供向剪辑软件交接的 XML 路径。 | 对我们最有价值的是返修时能回到确切底版。单换乐沿用锁画文件；换剪点才重算后续层。我们已有可复剪工程，本轮只吸收版本选择方法。Node 24、whisper.cpp 和跨软件 XML 交接未在本机作本次验收。 |

## 用《桂工转专业》检验这些做法

使用归档成片、同一期的 65 条人工校对字幕与已有逐词时码。取样检查与剪点模拟均读取原件。该样片与版本记录属于原工作区，未随公开技能分发。

| 复验位置 | 当场查到了什么 | 下一期实际怎么剪 |
| --- | --- | --- |
| 7.40–11.20 秒，校名与内容预告 | 同一个区间的六张取样帧先出现桥梁与代码，再出现校园雕塑，随后换成申请时间、绩点、面试三项。原答复里用户退过“校名主图上又放一遍校名”的版本。 | 交代学校时一个可认的地点就够。旁白进入预告后，换成承接三个问题的画面。产品介绍同理，展示产品全貌后，小窗只在需要读出细节时加。 |
| 30–41 秒，两年表格 | 区间图能辨出 2024、2025 的切换。另在 1280×720 导出的表格内部，同一块 880×252 像素区域取连续 16 帧，比较 15 对相邻帧的纵向位移。31.40 秒开始的窗口估得每帧上移 16–21 像素，37.00 秒开始约 33–34 像素，40.00 秒开始最匹配位移为 0。逐词识别把“桂工”写成“贵公”，校对字幕第 18 条已写对。 | 保留浏览过程，让关键条件停下来读。固定框在停稳后落下，切走前撤出。逐词数据供定位，专名按原表和校对稿显示。项目引用的政策与条件仍以当期原件为准。 |
| 88.92–94.62 秒，开发成果 | 第 48、49 条字幕的时段，画面从项目介绍和真实首页转到首页服务入口细节，此时没有角色压在 UI 上；随后口播换到面试建议，画面才转向敲键盘。 | 说“我开发了一个小程序”时保留作品画面。键盘镜头适合讲编程动作，单靠它看不出做了什么。把这条原因记在本期选材记录。 |
| 同一份字幕模拟删句 | 取 7.740–9.220 秒作**假设删段**。第 5 条完整落入删段；原第 6 条 9.280–10.780 秒换算到剪后 7.800–9.300 秒。真实成片仍沿用已批准的完整口播。 | 用户要求缩短采访时，可找回受影响的字幕与 B-roll；先判断是否删去了必要的指代。本例删掉学校名会使后面的政策失去适用对象，编辑应保留或在重组后补回出处。 |

区间图适合找“这一句放了什么”，连续帧比较适合查“究竟在滚，还是停着”。上面的位移是对固定区域的像素匹配估计，适合这个平面表格。声音波形用于定位，音效类别、配乐听感和受众数据没有在本次重测。[区间图与字幕换算的用法](review-and-learning.md)

我还用同一工具查了一个与校园无关的调色模板。已有样片的 4.90、6.033、7.167、8.30 秒四帧，从彩色书架过渡到同一画面的黑白／彩色并排。片里没有音轨，检查图明确标注，避免把这条直线错判为配音漏混。这次检验的是对比关系和审片工具；正式访谈的收音、人物选段仍需用实际访谈来验。样片未随公开技能分发。

## 还筛过哪些方案

- **prathameshp107/video-editing** 给素材弃用留理由，并有合成数据的跨画幅、语义定位测试说明。其测试报告区分“同一帧证据仍有效”和“实际可见内容是什么”，这项区别值得保留。未查到明确仓库许可，本轮只读。 [镜头日志](https://github.com/prathameshp107/video-editing/blob/b344da99bfaeb496c048703b82bf1a034d732f2a/templates/SHOT_LOG.csv) · [作者测试说明](https://github.com/prathameshp107/video-editing/blob/b344da99bfaeb496c048703b82bf1a034d732f2a/SKILL_TEST_REPORT.md)
- **OpenMontage 和 Clipper** 的长片选段可参考。前者先以整份转写找候选，再借场景变化校核边界；后者适合比较开头强度和片段独立性。对我们，选段解释能供编辑复核，打分只能帮助排序，不能当播放量预测。 [OpenMontage 选段流程](https://github.com/thecoldblooded/openmontage/blob/249a6cb9ddc65dc65afb3ea24fac1c2aa69c733e/skills/pipelines/clip-factory/script-director.md) · [Clipper 规则](https://github.com/marcxxv/clipper/blob/c4b0967c78a736b30754340fa4b7e48034c688e6/.agents/skills/clipping/SKILL.md)
- **OpenClip 和 OpenFilm** 分别解决托管取片和技能发现。OpenClip 的任务提交、状态与下载依赖付费服务；OpenFilm 的注册表便于找到其他实现。我们的缺口集中在怎么选镜和怎么验片，采用上面的本地方法就能推进。 [OpenClip 使用契约](https://github.com/OpenClip-App/agent-skills/blob/ea02c98db69c437616df1db4a4400cde1f4a0832/skills/openclip-clipping/SKILL.md) · [OpenFilm 注册表](https://github.com/openfilm/skills/blob/7ba2e95ae56015c26764622336eb46ae429aa12c/README.md)

现有的 HyperFrames 三种布局组件、源时码粗剪算法和通用横屏模板继续承担制作。下次遇到同类退回，在项目复盘记下原版、修改时码、用户保留哪版及原因；当同一条方法能在不同题材解决相同问题时，再更新通用规则。栏目自己的纸底、标题字和音乐保存在栏目技能中。[现有模板和用法](general-templates.md) · [上游代码、许可证与固定版本](../upstream/sources.md)

## 本轮文件

| 用途 | 在统一工作区的位置 |
| --- | --- |
| 研究结论、固定来源及直接复用的原件 | 本文、[来源和三份原件校验值](../upstream/sources.md)、[原审片脚本](../upstream/browser-use-video-use/timeline_view.py)、[许可证](../upstream/browser-use-video-use/LICENSE)、[拆片原说明](../upstream/gitethanwoo-video-editing/analyze-video-editing.upstream.md) |
| 下次调用时会读的指令 | [通用 Skill](../SKILL.md)、[调用入口说明](../agents/openai.yaml)、[选镜与备料](packaging-plan.md)、[粗剪与字幕](general-templates.md)、[审片及返修](review-and-learning.md) |
| 可执行的两个工具 | [剪后时码换算](../scripts/map_cues.py)、[换算回归测试](../scripts/test_map_cues.py)、[带画面、逐词和波形的审片](../scripts/review_window.py) |
| 来源 | [上游来源与许可](../upstream/sources.md) |
