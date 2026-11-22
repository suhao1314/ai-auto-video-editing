# 从工作台选进通用剪辑的工具

2026-11-22 对照“工具与 Skill”页面的 30 条原记录，选出 4 项可在本机直接用于剪片的工具。下列命令从技能目录运行；文件名替换为本期路径，输出选本轮的新文件名。阿桂和其他栏目共用这些工具。

| 剪到哪一步 | 我会调用什么 | 交回什么 |
| --- | --- | --- |
| 原始口播里存在长停顿 | Auto-Editor 标出声音活动范围，编辑标记要保留的无声操作 | 源时码的拟删区间、保护段、预计时长，供听看取舍 |
| 另交网页字幕，或整条字幕同样早／晚了一点 | Subtitle Edit 的本地命令行 SeConv 转换格式或整体平移 | 新字幕文件及首尾、正文、显示时间复核 |
| 改标题、人物位置或 UI，希望确认某块画面保持一致 | 在同一成片时刻用 Pixelmatch 只比较指定矩形 | 标出变化的图、变化像素数，定位到需要回看的区域 |
| 客户指定画幅、帧率模式、编码或声道 | MediaInfo 读取最终交付文件技术参数 | 对照委托规格；全片解码、音画同步和实际播放另核 |

## 原始口播的停顿粗剪

在装有本工具的电脑，便携入口为 [Auto-Editor 31.8.0](https://github.com/WyattBlue/auto-editor/releases)。先听原片是否带持续配乐、静默读表或操作演示。拿到锁定的成音时跳过声音裁切。原声中相同响度可能是呼吸、话尾或背景音乐，最终剪点要回到原话确认。源素材给绝对路径，避免换工作目录后找错同名文件。[固定版官方 Skill](https://github.com/WyattBlue/auto-editor/blob/31.8.0/skills/auto-editor/SKILL.md)

```powershell
$sourceVideo = (Resolve-Path -LiteralPath '原始口播.mp4').Path
$editorExe = 'auto-editor'
& $editorExe $sourceVideo --preview --no-cache
& $editorExe $sourceVideo --keep 2.1sec,2.5sec --no-cache --no-open -o '本轮候选剪点.v1'
python -X utf8 -B scripts/auto_editor_plan.py '本轮候选剪点.v1'
```

`--keep` 的秒数要换成本期源片中真实的必要动作。查看拟删段后，用已采用的时间线再运行 `auto_editor_plan.py`，把 JSON 传给 `map_cues.py - 源字幕.srt` 即可计算剪后字幕。适用同源、同序、原速的删剪。多源、多层或变速工程应读剪辑工程的实际时码。[剪点转换器](../scripts/auto_editor_plan.py) · [字幕映射](../scripts/map_cues.py)

本机用 9 秒、含三段声音的样例做对照。相同声音阈值、零边缘余量时，原候选保留 3.60 秒；指定保留源片 2.10–2.50 秒的静默段后，保留时长为 4.00 秒。这项验证的是保护段是否真的进入剪点，长采访里的语义取舍要听当期原话。

## 中文字幕换格式、校时

使用 [Subtitle Edit 的 SeConv 5.3.0](https://github.com/SubtitleEdit/subtitleedit/releases)。输出目录用本次项目的草稿目录。导出 WebVTT 可用于网页播放器；已有正确中文稿时直接保留原词。全片偏差一致才用 `--offset`。若越到后面越偏，用时长及头、中、尾的发音定位漂移；若从某一剪点突然错位，先核剪点和剪后时间。[官方 CLI 用法](https://github.com/SubtitleEdit/subtitleedit/blob/v5.3.0/docs/reference/command-line.md) · [官方同步说明](https://subtitleedit.github.io/subtitleedit/faq.html)

```powershell
$seconv = 'seconv'
& $seconv '校对稿.srt' webvtt '--output-folder:本期草稿' '--output-filename:网页字幕.vtt' --json
& $seconv lint '校对稿.srt' --json
# 仅当口播确实整体晚 150 毫秒，另写一份带偏移的字幕
& $seconv '校对稿.srt' subrip '--offset:150' '--output-folder:本期草稿' '--output-filename:试听校时.srt' --json
python -X utf8 -B scripts/check_export.py '本期成片.mp4' --require-audio --srt '本期草稿/试听校时.srt'
```

在《桂工转专业》上，SRT → WebVTT → SRT 后，65 条的原文和 130 个起止时间全部相同。试验副本整体延后 150 毫秒，首句从 0.240 秒变为 0.390 秒，末句结束于 120.750 秒，超出成片的 120.667 秒，成片时长检查定位到第 65 条。SeConv 的默认可读性检查对原片列出 10 处停留较短、11 处两句间隔较短，编辑应结合原声语速和字数看具体句子。贯穿原片的自然连读不必为了消除提示而挪开。

## 局部画面复查

选已确认的基准版本。在两个版本的同一画面状态取相同尺寸的帧，优先无损 PNG；变更过剪点时，先按台词或动作对齐。给定只需保持的矩形 `x,y,宽,高`，四个值均为最终画布的像素。将比较结果与差异图放在项目临时目录。[对比入口](../scripts/compare_roi.mjs) · [Pixelmatch 原项目](https://github.com/mapbox/pixelmatch)

```powershell
node scripts/compare_roi.mjs --baseline '定稿帧.png' --actual '待查帧.png' --roi 80,570,1100,108 --diff '差异.png' --report '差异.json'
```

区域应完整包住两个版本中待核的对象；查小窗是否挡按钮时选按钮区，查字幕移动时把原位置和新位置都圈进去。默认要求区域内零超阈值像素，`0` 表示通过，`1` 表示有超过容差的变化。转码、取帧时机和动态背景都会影响数字，看差异图再判断改动是否有意。像素检查无法判断字写得对不对或隐私信息能否辨认。这里复用工作区已有的 [随技能附带的 Pixelmatch 4.0.2 比较器](../tools/visual-regression/compare-images.mjs)。先在 `tools/visual-regression` 运行 `npm ci`；需要改用另一安装位置时才传 `--visual-regression-root`。工作台研究卡列的是上游 v8，其不同版本的差异数不可直接互比。

在 1280×720 的通用组件样片上，同帧对照为零变化；改用另一个画面时，指定的 640×360 区域中有 177,168 个像素超过阈值。另用受控样例将变化分别放在区域内外，只有区域内变化触发差异告警。

## 交片规格

正式文件可以直接用 [MediaInfo CLI 26.10](https://mediaarea.net/en/MediaInfo/Download/Windows) 读出各轨参数。检查帧率时看视频轨的 `FrameRate` 和 `FrameRate_Mode`；AAC 音轨也可能显示 `FrameRate`，该值是音频帧率。按用户约定判断是否需要 CFR、某种尺寸或采样率。只需验解码、时长和字幕的常规交付沿用已有的 `check_export.py`。[官方发行页](https://mediaarea.net/en/MediaInfo/Download/Windows)

```powershell
$mediaInfo = 'mediainfo'
$info = & $mediaInfo --Output=JSON '本期成片.mp4' | ConvertFrom-Json
$info.media.track | Select-Object '@type',Format,Width,Height,FrameRate_Mode,FrameRate,Duration,Channels,SamplingRate
```

本机在已归档的《桂工转专业》读到 MPEG-4 容器、AVC 视频、1280×720、30 fps 恒定帧率、3620 帧；音频是 AAC 双声道、48 kHz。两个轨道显示 120.667 秒。平台上传和设备播放效果需在对应平台或设备上验。

## 有对应任务时才选用的 5 项

| 任务 | 怎样用 |
| --- | --- |
| 查公开资料、政策出处和素材作品页 | Firecrawl 可在普通浏览无法高效提取正文时查公开信息，保留原始页面以便核对。要下载入片的图片、视频、音乐或图标，照常列具体作品给用户确认。本轮没有调用收费抓取。[官方用法](https://docs.firecrawl.dev/features/scrape) |
| 同规格的活动卡、对比卡要批量换文字或数据 | Satori 可将版式与内容渲染为 SVG，再按实际画幅导出成图。先试一张最长中文、确认字体和换行，再做全组；片头沿用已经定好的栏目字体。[原项目](https://github.com/vercel/satori) |
| 操作示意缺少统一图标 | Lucide 可补通用线形图标；先查可用本地库，需要联网取图标时仍先确认具体名称。真实产品按钮从当期录屏取。[官方指南](https://lucide.dev/guide/) |
| 课程口播已经有 Markdown 讲义 | Marp CLI 可把选中的章节导出逐页图片，在讲到对应概念时入画；软件操作仍需展示真实点击与结果。[官方 CLI](https://github.com/marp-team/marp-cli) |
| 用户明确要求浏览器本地选择、预读或剪切文件 | Mediabunny 的文件读取与转换可用于网页预处理；确定目标浏览器后用相同编码试文件，核对音画时长。现有桌面工程可继续用 FFmpeg。这次没有做浏览器或微信端实测。[官方文件读取](https://mediabunny.dev/guide/reading-media-files) |

其余 21 项的当前用途分别是网页与接口开发验证（Storybook、Grafana k6、Hurl、Lighthouse CI、Knip、fast-check、MSW、axe-core、DOMPurify、Dexie.js、Driver.js、Linkinator、Pagefind），文档整理（PDF Arranger、Paged.js、docxtpl），以及调研营销（Formbricks、Marketing-for-Founders、Agency Agents、PM Skills、Marketing Skills）。随包剪辑组件的版本与许可见[上游来源](../upstream/sources.md)。

## 本地维护入口

Auto-Editor 的两份官方 Skill 已随库存入。拿原始讲话做删停顿时读[原版剪辑指令](../upstream/auto-editor/editing.upstream.md)；要交可编辑剪点表时读[原版导出指令](../upstream/auto-editor/export.upstream.md)。两份取自[31.8.0 的固定提交](https://github.com/WyattBlue/auto-editor/commit/654a5138cd50767a63a6644c89c667e75d894d88)，附[源码许可证](../upstream/auto-editor/LICENSE)。上游还提供其他编辑器的工程导出，本次实测到本地剪点和字幕衔接，接收端软件的导入效果须另外开工程确认。

工作流入口在[通用剪辑 Skill](../SKILL.md)。两份适配的回归用例在[剪点测试](../scripts/test_auto_editor_plan.py)和[区域比较测试](../scripts/test_compare_roi.mjs)。Auto-Editor、SeConv 和 MediaInfo 需在使用机器自行安装；测试和成片文件保存在用户项目内。
