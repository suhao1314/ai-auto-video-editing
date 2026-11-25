# AI 自动剪辑

把选题、录屏或上一版审片交给你常用的 AI，说说这次想拿到什么。只给一个产品名，它会查官方资料、社区反馈和近期作品，推荐一个值得拍的角度。已有定稿旁白就按原声排画面；审片时指出哪里没看清，就能按时码返修。适合做口播、教程、访谈和校园科普的人。

这里的 **Skill 是 AI 可以阅读的剪辑说明**。能读文字的 AI 就能用它写分镜、列补拍清单；能读取音视频并调用剪辑工具的 AI，还可以按原声校时、剪片和检查导出。**原创内容仅限非商业使用。** [使用许可](LICENSE)

## 直接发给你常用的 AI

复制下面这段到聊天框，把最后一句换成你的题目和现有素材。能打开链接的 AI 可以直接读仓库。

```text
请按这个仓库里的剪辑说明帮我做一期视频：
https://github.com/suhao1314/ai-auto-video-editing
从 skills/ai-video-editing/SKILL.md 开始，按我手头的材料接着做。
这期教同学导出报表。我有一段录屏和定稿旁白，想让大家能听着我的话跟着点。
```

**AI 打不开链接时**，打开下面的纯文本入口，把正文复制进聊天，附上文案或转写就能开始。校园片把两份都贴进去。支持附件的 AI 也可以接收这些文件。只有文字时先做估时分镜；能读取旁白后，再换成真实时码。[通用说明原文](https://raw.githubusercontent.com/suhao1314/ai-auto-video-editing/main/skills/ai-video-editing/SKILL.md) · [校园说明原文](https://raw.githubusercontent.com/suhao1314/ai-auto-video-editing/main/skills/agui-horizontal-video/SKILL.md) · [逐句分镜与备料表](skills/ai-video-editing/references/packaging-plan.md)

**AI 可以读本地文件时**，解压仓库，让它读取 `skills/ai-video-editing/SKILL.md`，按需打开同目录下的 `references` 和 `scripts`。校园片再读同级的 `agui-horizontal-video/SKILL.md`。把本期素材放在自己的项目目录，告诉 AI 去哪里找。[下载完整仓库 ZIP](https://github.com/suhao1314/ai-auto-video-editing/archive/refs/heads/main.zip)

## 为什么用这套流程剪

| 剪到哪一步 | 你能拿到什么 |
| --- | --- |
| “想做一期 Muse，先看看拍什么好” | 一份能挑题的清单：哪个问题值得拍、为什么现在拍、参考哪条作品的哪一段、自己的第一镜拍什么。每条热度依据带平台和日期，看过的镜头与作者标注的章节分别交代。[选题调研、热点与参考视频](skills/ai-video-editing/references/topic-research.md) |
| 只有选题，要做短视频教程 | 从你发过的作品里找口吻，从同受众的优质片里看什么时候给答案。钩子过后直接展示第一步，例如把光标移到搜索框、输入观众要找的词。[抖音口播写法](skills/ai-video-editing/references/douyin-spoken-scripts.md) |
| 开剪前，判断素材够不够 | 一张按句排列的分镜表。每句写清原话、要展示的动作、素材及源时码。已有录屏、需要补拍的实物、拟下载的网素材分开列，便于你一次确认。 |
| 粗剪时，保住真正有用的停顿 | 原始口播可以先标出重复和长停顿，供编辑复听。教程里等待文件生成的两秒即使没人说话，也可以标记保留。已有定稿配音时，直接沿用它的停顿和内嵌音效排画面。 |
| 有定稿人声，想让观众看清每一步 | 找到关键词说出口的时刻，让录屏依次给出点击前、操作中和结果。讲长网页时滚到原文并停住；看最终导出，确认结果留够阅读时间，点击声落在按下的那一刻。[操作镜头与声画核验](skills/ai-video-editing/references/tutorial-evidence.md) |
| 审片时，把反馈落到一处剪点 | 可以直接说“第 35 秒这行还没读完，多停一会儿”。按该句回看前后镜头，改停留和字幕出点，导出后检查字幕是否越过片尾、音轨是否存在。 |

**看一个镜头怎么剪。** 教程里说“我点一下这里，把报告导出来”，先给完整界面，让观众认出按钮在哪；说到“导出”再推近，保留一次点击声。下一句“文件已经在这儿了”继续用同一段录屏，停在新增文件上，让人看清结果。这两句在随包的八秒样例里都有画面、字幕和声音安排。[查看三句分镜样例](skills/ai-video-editing/assets/plan-example.json)

## 两套 Skill 怎么选

- **通用 AI 视频剪辑**适合教程、访谈、口播和测评。上面的报表教程就是通用版的调用示例。也可以对它说“从这段访谈里挑两段能独立听懂的故事，给我原片入点、出点和必须保留的上下文”。[通用剪辑说明](skills/ai-video-editing/SKILL.md)
- **阿桂校园知识**在通用流程上增加校园事实核验、连续滚表、角色让位和隐私遮挡。可以直接说“按阿桂校园说明剪一期转专业科普，用我提供的两年政策录屏分别向下滚，讲到条件就停住；绩点样本先遮姓名学号，再放大。先把逐句安排发我”。阿桂真实素材与配乐保存在作者本地，使用者自备获准使用的实拍、图形和声音。[校园剪辑说明](skills/agui-horizontal-video/SKILL.md) · [本地素材表](skills/agui-horizontal-video/references/asset-map.md)

## 想把 Skill 安装到工具里

支持导入 Skill 的工具，可以按该工具的说明导入完整目录。通用版可以单独用；校园版会读取通用版，请将两个目录并排保留。

### 安装到 Codex

在 Codex 对话里粘贴下面两行，安装后新开对话，直接描述剪辑任务即可。也可以用 `$ai-video-editing` 或 `$agui-horizontal-video` 点名选用。

```text
请用 $skill-installer 从 GitHub 仓库 suhao1314/ai-auto-video-editing 的 main 分支安装：
skills/ai-video-editing 和 skills/agui-horizontal-video。
```

手动安装时，将解压后的两个 Skill 目录复制到 Codex 的技能目录。Windows 默认在 `%USERPROFILE%\.codex\skills`，macOS 和 Linux 默认在 `~/.codex/skills/`。设置过 `CODEX_HOME` 时，使用其下的 `skills/`。已有同名目录时，先核对自己的修改。

### 运行本地脚本

在仓库根目录执行下面的命令，可以用 Python 3 检查上面的三句分镜。实际剪片和检查导出需要本机或 AI 环境可以调用 FFmpeg、ffprobe 或相应剪辑工具。[工具与用法](skills/ai-video-editing/references/workbench-video-tools.md)

```sh
python skills/ai-video-editing/scripts/check_plan.py skills/ai-video-editing/assets/plan-example.json
```

## 使用许可

原创 Skill、脚本和模板可用于学习、课程作业和非营利校园科普。付费代剪、广告赞助、带货、制作变现视频或集成到收费产品，须事先取得权利人的书面授权。第三方组件遵循各自许可证。[非商用许可全文](LICENSE) · [第三方来源与许可](skills/ai-video-editing/upstream/sources.md)
