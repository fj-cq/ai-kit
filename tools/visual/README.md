# Visual · 图形与页面视觉工具

根据要回答的问题选择图形，使用明确数据或关系生成可复核的 SVG/HTML。主题、绘制器、模板和示例统一在此维护。

## 选择路线

- 文字或表格已经清楚：不强制配图。
- 数量比较、趋势、贡献、流程、分工等：使用 [19 类绘图说明](renderers/consulting/GUIDE.md)。保留原来的容量、输入合同、数值和关系校验。
- 技术架构模型：使用 [架构绘制器](renderers/architecture/README.md)（0.1.0-draft），自动布局、节点避障和 JSON/SVG/HTML 导出；适用容量与限制见说明。
- 超出容量或需要特殊结构：使用 [SVG 原语](renderers/svg_diagram.py) 定制或拆图，不为套模板删关系。
- 适合正文流的布局：参考 templates/ 的 HTML 片段。它们是样例，不是统一数据 API。
- 地理取点与边界：读 [地图组件说明](renderers/geographic/GUIDE.md)。Leaflet 与带来源的 GeoJSON 需要另备，此包未提供地图引擎与边界数据。

## 实际运行

Python 3.9+，咨询图仅使用标准库，无需网络或账号。以下命令从仓库根目录运行；输出必须选新的路径，不能写入 tools/visual 或覆盖旧文件。

```sh
python3 tools/visual/render.py --list
python3 tools/visual/render.py --architecture --input prompts/architecture-diagram/examples/autoloop/model.json --output-dir outputs/architecture --theme white
python3 tools/visual/render.py --list-themes
python3 tools/visual/render.py --case quantity-waterfall --theme coffee --output outputs/waterfall.svg
python3 tools/visual/render.py --input private-inputs/input.json --theme midnight --output outputs/custom.svg
python3 tools/visual/render.py --gallery outputs/visual-gallery --theme white
python3 tools/visual/renderers/consulting/render.py --self-test
python3 tools/visual/tests/test_themes.py
```

`--theme` 接受主题 ID 或中文名。未知主题会报错。主色自定义在 themes.json 定义完整主题后使用，当前 CLI 不提供任意单色覆盖参数。

## 主题与图形的边界

[15 套主题](themes/themes.md) 的 JSON 是参数源，CSS 从它生成。公共 render.py 将主题应用于图形及图册的颜色，保留原布局、坐标、数据和文字；底层 consulting/render.py 保持原固定配色，供回归比较。

原有咨询绘制器仍固定 1000×560；新增架构绘制器根据模型动态计算画布。咨询图不会因切换主题自动变成任意画布。页面字体与间距参数供页面模板使用，不代表所有 SVG 自动改变字体或布局。金色标记保留其强调用途，颜色不作为唯一语义。

最终网页将使用到的 CSS 和 SVG 内嵌；不能把只存在于本机的资源链接交给读者。重复嵌入同一 SVG 时确保 ID 唯一。打印、长标签和窄屏须在实际产物检查。

## 模板与外部依赖

11 个 HTML 示例在 templates/。其中 mindmap-mermaid.html 已改成无需脚本的离线概念树，保留旧文件名以兼容原链接；不再加载 Mermaid。其他模板也需按实际内容替换示例和检查资源，不把样例署名当真实来源。

本轮未迁入 200 个外部 SVG 图标、品牌专用文件、AI 图片生成工具及私人表达规则；核心咨询绘制器不依赖它们。需要这些资源时另行审核来源与依赖，不能声称完整覆盖所有旧 Visual Kit 路线。

## 状态与来源

版本 0.2.0-draft，实验。绘图代码与原语来自维护者的现有视觉库，保留其算法并做路径和主题适配；维护者已确认自编部分为自行／AI 辅助编写，按项目许可管理；Leaflet 等第三方依赖及地理数据另按其许可核实。测试通过说明指定输入合同成立，不认证业务数据真实，也不等同于全图型浏览器验收。

相关任务：[文字稿转图文网页](../../prompts/text-to-visual-page/README.md)。
