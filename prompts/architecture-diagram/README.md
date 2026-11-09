# 技术架构图生成

把技术材料整理成系统、模块组、组件和关系，默认先用图片生成功能产出视觉稿，再用代码复刻为可编辑图并修复局部。图片功能不可用时直接走纯代码流程。适用于技术设计沟通、系统边界说明和接口关系审查。

流程版本：`0.2.0-draft`，实验能力。JSON 合同与 Python 绘制器仍为 `0.1.0`。自然语言建模、图片调用与代码复刻由当前 AI 和宿主工具完成；Python 绘制器只接收 JSON，不会自行理解文档、生成图片或自动追踪位图。

## 开始使用

1. 复制 [完整提示词](prompt.md)，附上技术材料、目标读者和要解释的问题。无需历史会话或原参考图片。
2. 核对范围、关系覆盖表与待确认项，区分组件、能力、步骤和外部系统。图片功能可用时，按[中等详细度模板](image-prompt.md)列出模块、主要关系、关键边界与浅色分栏卡片风格，先生成一张图片；没有参考图也能执行。
3. 查看生成图片，再以它为视觉底稿、材料与模型为语义依据，用 SVG、HTML/CSS 等代码复刻；保留可用版式，修复错字、漏项、连线和遮挡，交付图片、实际提示词、可编辑图与模型。把位图嵌入 SVG 不算复刻。只要求模型或明确指定纯代码时遵从用户范围。
4. 没有图片功能，或实际调用失败且本轮无法恢复时，说明原因并直接走纯代码流程。将 JSON 存到 `private-inputs/architecture.json`，从仓库根目录执行：

```sh
python3 tools/visual/render.py --architecture --input private-inputs/architecture.json --output-dir outputs/architecture --theme white
```

上述纯代码绘制器需要 Python 3.9+；只用标准库，不联网、不要求账号，不调用付费服务。图片生成使用宿主已有功能及其权限，不由此脚本调用。输出目录必须不存在，不覆盖已有文件。绘制器输出 `diagram.svg`、可离线浏览的 `index.html`、可编辑的 `model.json`、带告警的 `report.json`。自动布局可作底稿，但不保证复刻图片版式；图片路线需要由 AI 编写或调整代码，修改后同步核对 SVG/HTML，不沿用旧布局报告冒充新版验证。

纯文本 AI 环境可独立完成 JSON 建模；不能执行命令时不要宣称已生成图。修改 model.json 后重新导出到新目录即可重载编辑；本版没有拖拽编辑器。

## 三个独立建模案例

均为专为本能力编写的虚构材料，使用同一份冻结提示词，经三个独立 AI 会话生成模型，不代表真实系统已验收。

| 案例 | 输入与模型 | 主要考察 |
| --- | --- | --- |
| 自动任务闭环 | [输入](examples/autoloop/input.md) · [模型](examples/autoloop/model.json) · [核对](examples/autoloop/model-review.md) | 三组、调用与结果反馈、多回路 |
| 补货建议 | [输入](examples/supply-chain/input.md) · [模型](examples/supply-chain/model.json) · [核对](examples/supply-chain/model-review.md) | 六组、人工步骤、外部系统、未知关系不补造 |
| 数字展览 | [输入](examples/museum/input.md) · [模型](examples/museum/model.json) · [核对](examples/museum/model-review.md) | 八组、中心辐射、资源下发与故障反馈 |

例如：

```sh
python3 tools/visual/renderers/architecture/validate.py prompts/architecture-diagram/examples/autoloop/model.json
python3 tools/visual/render.py --architecture --input prompts/architecture-diagram/examples/autoloop/model.json --output-dir outputs/autoloop --theme midnight
```

## 如何验收

先逐条对照原材料检查实体、归属、边界和关系；每条明确关系必须有材料依据。图片路线另检查生成图片与代码复刻图的布局保留、文字与关系修复，图片里的错误不得变成模型事实。自动校验只查合同与引用，不能证明证据内容支持结论。再看浏览器里的字、线、编号和关系索引，检查缩放与导出。

关系标签保留在图右侧索引及网页表格，图中用编号对应。依赖、反馈与证据状态有文字说明，不只用颜色区分。报告会列交叉、共线、编号仅在索引的情况；有告警不等于所有布局都不可用，也不能忽略告警直接称验收通过。

[实际验证与 UAT 状态](../../docs/architecture-diagram/validation.md) 分别记录自动化、浏览器、独立 AI 与人工验收，包含首轮失败。

## 范围与限制

Python 绘制器单图最多 12 组、48 节点、72 关系；支持分层、线性、中心辐射及反馈边。每节点属于一个组，每组最多一个边界。不支持嵌套/重叠边界、多重归属、时序语法、物理部署拓扑自动推断或程序化图片识别。图像理解和代码复刻依赖使用者的 AI 及宿主功能。图片先行并不保证文字与连线准确，仍须核对；本版未提供自动图片转 SVG 的 CLI。新流程与历史纯代码验证的覆盖分别见验证说明。

自动布线避开节点和组标题，尽量减少交叉，但不是任意拓扑的最优求解器。密集回路可能共线或交叉；超限会拒绝，布线失败会报错，不会偷偷删边。此时应按明确范围拆图并保留总关系清单。实际大小保证文字尺寸，较大图需滚动或缩放；适应宽度可能使文字变小。

与 [文字稿转图文网页](../text-to-visual-page/README.md) 的区别：本能力建立技术关系模型；后者忠实呈现已经定稿的文字。

## 来源

提示词、模型合同、布局和导出代码为本项目本次编写；主题与 SVG 原语复用 Visual。案例全部虚构，不含真实公司材料或外部架构图。按项目 [许可边界](../../LICENSING.md) 使用。
