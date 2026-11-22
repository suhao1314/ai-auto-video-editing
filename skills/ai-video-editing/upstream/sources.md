# 上游来源与取用边界

本目录保存固定版本的上游说明、选中的实现和许可证。技能入口快照使用 `.upstream.md` 后缀，项目从通用技能入口选用。以下提交链接可回查到原作者对应版本。

## 工作台筛入的剪辑和导出 Skill

[Auto-Editor 31.8.0 固定提交](https://github.com/WyattBlue/auto-editor/tree/654a5138cd50767a63a6644c89c667e75d894d88)提供[原剪辑 Skill](auto-editor/editing.upstream.md)、[原导出 Skill](auto-editor/export.upstream.md)和[许可证](auto-editor/LICENSE)。原文件 SHA-256 依次为 `bef5e21914f7464092ea4d62fb7510a4f14a1c9b80f77f0e2d33265eb059791c`、`8d3adf9302e38b755ffafecde39551b3f4a21db161491f1d80b237a222bac2d0`、`ca2abdf695884c77ea4b4a5b64ca7b732d9d9dbade4eebc1c2e76c53e9e3bc83`。源码使用 Unlicense，发行二进制中各组件另按所附条款。SeConv、MediaInfo 和本机 Pixelmatch 的实际版本、路径、适用环节和可复查命令见[工作台剪辑工具](../references/workbench-video-tools.md)。

## 2026-11-22 剪辑工作流对照

[逐项研究和本地复验](../references/editorial-benchmark.md)列出七套主查项目、其余筛选记录、出处和各自的适用条件。本次有三份新文件直接从对应提交取得，逐件与 GitHub 树中的 blob 比过，均保留原字节。

| 固定来源 | 本机文件 | Git blob SHA-1 |
| --- | --- | --- |
| [Browser Use · 局部审片工具](https://github.com/browser-use/video-use/blob/43cfc566833548093455c9d4a46bd69913b7e552/helpers/timeline_view.py) | [原脚本](browser-use-video-use/timeline_view.py) | `0b8f72a71ebc168555242f7f087b3ebb92f79d53` |
| [Browser Use · MIT](https://github.com/browser-use/video-use/blob/43cfc566833548093455c9d4a46bd69913b7e552/LICENSE) | [原许可证](browser-use-video-use/LICENSE) | `271d8e2807d0d79aee85a231f5c9dbb007902783` |
| [Ethan Woo · 拆参考片](https://github.com/gitethanwoo/video-editing/blob/8b633c2d698410e523f95335aa6433766264cc7f/skills/analyze-video-editing/SKILL.md) | [原方法说明](gitethanwoo-video-editing/analyze-video-editing.upstream.md)，沿用同提交的 [MIT](gitethanwoo-video-editing/LICENSE) | `184bc5c00a4e55aaa1dd1f25b476ea82c5bea0dd` |

[本机审片入口](../scripts/review_window.py)直接调用原脚本的区间渲染函数，另行处理 Windows 中文字体、两种逐词结构和新文件输出。拆参考片快照用于阅读方法，其中指向上游相邻脚本的命令可到原仓库查阅。其余项目借鉴编排和审片决策，具体固定路径见对照文档。

## 2026-11-22 加入通用模板

| 来源和固定版本 | 取到本机的文件 | 本地用法和验证 |
| --- | --- | --- |
| [HyperFrames Registry Skill](https://github.com/heygen-com/hyperframes/blob/40cc86252d80ebc0daaf3db373b13d339f8c13f8/skills/hyperframes-registry/SKILL.md)，HeyGen，Apache-2.0 | [注册表原说明](heygen-hyperframes/registry/SKILL.upstream.md)、三个布局的原 HTML 与参数登记。两个带插槽的组件附原 README。[许可证](heygen-hyperframes/LICENSE) | 直接取姓名条、前后对比、窗口切屏三份实现。[本地预览入口](../scripts/preview_component.py)把自己的图片和中文字段送入原组件，依赖改从本机读取。在 Chromium 分别用原组件声明的 GSAP 3.14.2 和本机已有的 3.15.0，验证姓名条进出、两图加载与 50% 对比分界、窗口切到第二张图。两组均无外部请求。GSAP 由运行环境提供。 |
| [Talking-head video-editing-skill](https://github.com/social-media-skills/video-editing-skill/tree/f94d0517d717de281ee23569094aac616d32f4ef)，Frank Heijdenrijk，MIT | [原技能](social-media-video-editing/SKILL.upstream.md)、[原剪辑算法](social-media-video-editing/edit_video.py)、[许可证](social-media-video-editing/LICENSE) | 取其专门的源时码与删剪理由处理。[本地入口](../scripts/rough_cut_plan.py)复用原算法计算声音能量、镜头变化和候选区间，加上中文默认值及完整保留段校验。使用 9 秒本地样例同时跑过上游 `--plan` 与本地入口，上游把没说话的结尾列为拟删，本地入口完整保留所指的 8–9 秒。这里只实测了粗剪提案。 |

模板代码按 GitHub 固定提交的 Git blob 哈希逐件核对，HTML、参数文件与上游原文均按原字节保存。[姓名条源码](https://github.com/heygen-com/hyperframes/blob/40cc86252d80ebc0daaf3db373b13d339f8c13f8/registry/blocks/lt-clean-bar/lt-clean-bar.html) · [对比组件](https://github.com/heygen-com/hyperframes/tree/40cc86252d80ebc0daaf3db373b13d339f8c13f8/registry/components/before-after-wipe) · [演示窗口](https://github.com/heygen-com/hyperframes/tree/40cc86252d80ebc0daaf3db373b13d339f8c13f8/registry/components/browser-device-stage) · [粗剪源码](https://github.com/social-media-skills/video-editing-skill/blob/f94d0517d717de281ee23569094aac616d32f4ef/skills/video-editing-skill/scripts/edit_video.py)

本地 FFmpeg 横屏模板由工作区自制，适合直接导出静音 B-roll。组件的 Apache 或 MIT 许可针对相应源码。每期实际用的实拍、音乐和字体沿用各自的来源与用途记录。

## 已摘录

| 上游 | 固定提交 | 许可证 | 本轮取用 |
| --- | --- | --- | --- |
| [gitethanwoo/video-editing](https://github.com/gitethanwoo/video-editing) | 8b633c2d698410e523f95335aa6433766264cc7f | MIT，Ethan Woo | 源媒体观察、时间轴、逐句 B-roll manifest、低清审片、转场条带和最终解码校验 |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | 40cc86252d80ebc0daaf3db373b13d339f8c13f8 | Apache-2.0，HeyGen, Inc. | 可复现逐帧时间线、可编辑图层、确定性动效、文字安全区、音乐和音效只为可见动作服务 |

2026-11-21 首次取用的是上表两套方法的说明与许可证。

## 未复制的参考

[remotion-dev/skills](https://github.com/remotion-dev/skills) 固定提交为 6f55706d1069e512430582ad86e4e57dc07afe1b。它对时间轴、字幕、转场、音效和像素效果有直接参考价值。仓库根目录未发现许可证文件，故本地只登记链接和提交，不复制其文本。

## 完整性

| 文件 | SHA-256 |
| --- | --- |
| gitethanwoo-video-editing/SKILL.upstream.md | 0EC528C3657E0DDAD7C3B632B831D22BC5461E48716E783F7773785884AC4BA4 |
| gitethanwoo-video-editing/find-broll.upstream.md | 7BEF21C2812224E02A1118408AB69EC65CF0859B76311E4B41CD25EE3BAD4CD5 |
| gitethanwoo-video-editing/LICENSE | 3214A54C719AB6F22F3A084A7766DF1A6D9B43F97DBC2D822147D83F352A67B8 |
| heygen-hyperframes/SKILL.upstream.md | B0F406B01C09D60CF8F50DFD6ADF994F45B47F4F709DE66F5E52B2D09B9B3153 |
| heygen-hyperframes/media-use.upstream.md | 2EEF0B69AB75E54481FF73B6617B70CB0B7AC620A993E7996248C3A80FEE558E |
| heygen-hyperframes/LICENSE | 4259155FB06F127687EE7B0A8A3682D45132DB0F2DA26CBC0B7A2D1E796436B8 |

后续更新要重新确认提交、许可证、文件哈希和改动内容。上游的网络调用、遥测、账户、安装或渲染命令不因文字参考而获得执行授权。
