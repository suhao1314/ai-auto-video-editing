# AI 自动剪辑

用文案、旁白和真实素材剪口播视频。通用 Skill 负责逐句分镜、选材、字幕、声音和审片。阿桂校园知识 Skill 在这套流程上增加校园事实核验、横屏版式、角色站位和录屏打码。

**本仓库的原创 Skill、脚本和模板仅限非商业使用。** 可以用来学习、做课程作业和非营利校园科普。付费代剪、广告赞助、带货、使用这些工具制作变现视频或集成到收费产品，均须事先取得权利人的书面授权。第三方组件遵循各自许可证。[非商用许可](LICENSE) · [第三方来源与许可](skills/ai-video-editing/upstream/sources.md)

## 安装到 Codex

在 Codex 对话里粘贴下面这句话，就能把两套 Skill 装在一起。安装完成后，新开一个对话，使用下一节的调用示例。

```text
请用 $skill-installer 从 GitHub 仓库 suhao1314/ai-auto-video-editing 的 main 分支安装两个目录：skills/ai-video-editing 和 skills/agui-horizontal-video。
```

**手动安装**也可以。下载后按下面三步操作，全程无需登录 GitHub。[下载 ZIP](https://github.com/suhao1314/ai-auto-video-editing/archive/refs/heads/main.zip)

1. 解压 ZIP，打开里面的 `skills` 文件夹。
2. 将完整的 `ai-video-editing` 和 `agui-horizontal-video` 两个目录并排复制到 Codex 的技能目录。Windows 默认为 `%USERPROFILE%\.codex\skills\`，macOS 和 Linux 默认为 `~/.codex/skills/`。设置过 `CODEX_HOME` 的用户复制到该目录下的 `skills/`。如果已有同名目录，先核对版本，保留自己的修改。
3. 新开对话，输入 `$ai-video-editing` 或 `$agui-horizontal-video`。只剪通用视频可以单装前者，校园版会读取同级的通用版。

## 怎么调用

**通用剪辑**适合口播、教程、采访和产品演示。把文件放进当前项目，将示例中的文件名换成自己的。[通用 Skill](skills/ai-video-editing/SKILL.md)

```text
用 $ai-video-editing 剪一条报表导出教程。旁白是“教程配音.wav”，操作是“导出录屏.mp4”。先按原声给我逐句时间轴，标出鼠标点哪里、何时放大、结果停多久。需要下载的素材先列清单给我确认。
```

**阿桂校园知识**适合非营利校园指南。使用者自备有权使用的校园实拍、角色图、屏幕录制和声音。阿桂的真实素材及配乐只保存在作者本地，公开仓库提供剪法和空白素材表。[校园 Skill](skills/agui-horizontal-video/SKILL.md) · [本地素材表](skills/agui-horizontal-video/references/asset-map.md)

```text
用 $agui-horizontal-video 做一期转专业校园科普。我提供“旁白.wav”“去年政策录屏.mp4”和“今年政策录屏.mp4”。两年的表格分别连续向下滚，讲到哪一行就停在哪一行。先列逐句画面、遮挡范围、角色站位和音效落点，缺哪一镜告诉我。
```

第一轮会拿到逐句分镜和素材缺口。定稿后可以直接说「按这版，素材核实后开剪」。网站素材按已确认的条目下载，成片按实际旁白对齐字幕。

## 本地剪辑工具

写文案和分镜可以直接开始。需要实剪或验片时，准备 FFmpeg 和 ffprobe。仓库附带的方案检查脚本可用 Python 3 运行，在解压后的仓库根目录执行以下命令即可检查一个三句分镜样例。其他工具按要做的步骤选用。[剪辑工具与用法](skills/ai-video-editing/references/workbench-video-tools.md)

```sh
python skills/ai-video-editing/scripts/check_plan.py skills/ai-video-editing/assets/plan-example.json
```
