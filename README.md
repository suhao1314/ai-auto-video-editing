# AI 自动剪辑

把文案、录音和素材整理成可审的逐句分镜，再剪成片。这个仓库有两个入口。

| 我要剪什么 | 选哪个 Skill |
| --- | --- |
| 口播、采访、产品演示、教程、测评，或从长访谈中选短片 | [通用 AI 视频剪辑](skills/ai-video-editing/SKILL.md) |
| 横屏的阿桂校园知识、新生指南或校园榜单 | [阿桂校园知识](skills/agui-horizontal-video/SKILL.md)，搭配同级的通用 Skill |

## 从一句话开始

**通用教程**　「用 `$ai-video-editing`。这段录屏教人导出报表，旁白已经录好。按原声列逐句时间轴，标出什么时候推近按钮、什么时候展示导出结果。需要网素材的话，先把具体条目发我。」

**阿桂校园**　「用 `$agui-horizontal-video` 做一期桂工转专业。我给你两年的表格录屏和一份配音。把两段连续下滑的时码列出来，绩点镜头先遮住个人信息，片头参考我提供的正式成片。」

已有稿子、配音或确认过的分镜，就从对应步骤接手。交分镜时，每句对应源素材、画面布局、动效、转场、字幕和声音。实际下载网站素材前确认具体条目。收到“素材核实后直接剪”，就沿用这一版授权。

## 在新电脑上使用

用有仓库访问权限的 GitHub 账号登录 GitHub CLI，运行以下命令。也可以在 GitHub 网页下载 ZIP，解压后进入含本 README 的目录。

```sh
gh repo clone suhao1314/ai-auto-video-editing
cd ai-auto-video-editing
```

可以直接让能读取本地文件的 AI 读取上表对应的 `SKILL.md`。要让 Codex 在新会话自动发现这两套 Skill，在 Windows PowerShell 中从仓库根目录执行以下命令。已装过同名技能时，命令会报告现有位置，便于核对版本。

```powershell
$skillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $HOME '.codex/skills' }
$skillNames = 'ai-video-editing', 'agui-horizontal-video'
foreach ($name in $skillNames) {
    $target = Join-Path $skillRoot $name
    if (Test-Path -LiteralPath $target) { throw "已有同名技能，请先核对现有版本：$target" }
}
New-Item -ItemType Directory -Force -Path $skillRoot | Out-Null
foreach ($name in $skillNames) {
    Copy-Item -LiteralPath (Join-Path 'skills' $name) -Destination $skillRoot -Recurse -ErrorAction Stop
}
```

两个目录放同一级。前期规划和分镜可以直接使用。可用 Python 3 从仓库根目录试验随附方案，检查它是否覆盖全部口播句及待备素材。

```sh
python skills/ai-video-editing/scripts/check_plan.py skills/ai-video-editing/assets/plan-example.json
```

剪片和审片时按任务选工具。处理音视频先确认本机可以调用 FFmpeg、ffprobe；需要停顿粗剪、字幕格式转换或导出规格检测时，查看[工具与用法](skills/ai-video-editing/references/workbench-video-tools.md)。新电脑做阿桂片，先按[栏目素材表](skills/agui-horizontal-video/references/asset-map.md)指定自己的正式参考片、纸底、贴纸和获准使用的常驻配乐。真实录屏和原声按期提供。

## 维护与来源

跨栏目的改进写入通用 Skill，例如同一句的声画对齐、口播粗剪和审片。纸底、标题字样、阿桂站位、校园事实核验留在校园 Skill。每次根据正式成片回填有效改法，下次开剪时可以追到具体镜头。

上游模板和脚本的版本、作者及许可在[来源登记](skills/ai-video-editing/upstream/sources.md)。拍摄素材、字体、音色和音乐按各自授权使用。
