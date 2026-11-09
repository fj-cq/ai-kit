# Architecture renderer · 0.1.0-draft

三层互不替代：提示词从材料建模；schema.json 与 validate.py 检查合同及引用；layout.py 与 render.py 负责布局、布线和导出。程序不调用 AI，不判断材料事实真假。

上层[架构图流程](../../../../prompts/architecture-diagram/README.md)默认先用宿主图片功能出图，再由 AI 用代码复刻并修复局部；本绘制器保持 JSON 输入，作为纯代码回退或复刻底稿，不负责图片生成或自动图片转 SVG。修改导出 SVG 后须同步核对 HTML 中的图与下载文件，原 report.json 不再证明修改后的布局。

## 合同与运行

模型见 [JSON Schema](schema.json)，采用 [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) 描述结构。标准库校验器实现本文件实际使用的关键字子集，并补充全局 ID、非空分组、归属、证据来源、待确认关联和关系去重检查；不宣称为通用 JSON Schema 实现。额外属性拒绝，避免把用户坐标当成布局输入。

```sh
python3 tools/visual/renderers/architecture/validate.py prompts/architecture-diagram/examples/museum/model.json
python3 tools/visual/renderers/architecture/render.py --input prompts/architecture-diagram/examples/museum/model.json --output-dir outputs/museum --theme white
python3 -B -m unittest discover -s tools/visual/tests -p 'test_architecture.py' -v
```

Python 3.9+，无需第三方包。CLI 成功返回 0，有模型、输出路径或布线错误返回 2；布局告警写 report.json 并输出到终端，成功退出不表示全部 UAT 通过。输入 JSON 拒绝重复键；输出要求新目录，禁止写入 tools/visual。

## 布局策略

- 根据文字长度换行并计算节点/分组高度；不截断长标签。
- 先按边界分区，确保包围框不会圈入无关组；边界优先于全图拓扑排布，分区分别布局。
- 分层模式优先以调用、数据流构建无环的排布骨架，再计算层级；形成回路的边仅不参与排序，仍全部布线。强连通分量缩合用于层级计算；线性模式按层级排序；辐射模式以关联最多的组为中心，随组数调整半径。auto 对明显中心结构选择辐射，其余分层。
- 关系方向仍以模型为准；反馈不参与层级估计，但全部渲染。布线使用按对端位置排序的四向端口，在节点和标题周围的稀疏坐标网格上搜索直角路径，加入转弯、交叉与共线路径代价。
- 通过现有 SVG 原语绘制节点和正交线。完整标签放在索引，图上用编号关联，避免把长句压在线上。

schema 的结构检查与业务语义是不同层次。例如把错误材料号填进 evidence.sources，即使引用存在，机器也无法证明这段材料支持关系。需要人或独立评审逐条核对。

## 编辑与导出

`model.json` 保留全部语义，可修改后重新导出；`report.json` 包含计算后的节点框和路径，用于检查而非输入合同。`diagram.svg` 内嵌样式，可单独打开；`index.html` 离线包含图、证据、待确认及缩放操作，下载链接依赖同目录三个文件。没有外部脚本、字体、网络依赖或拖拽编辑器。重复将同一 SVG 嵌入一个文档时，调用方需处理 SVG ID 命名空间。

## 限制

最多 12 组、48 节点、72 关系；边界仅支持互不嵌套的一级分区。复杂密集图可能交叉、共线；告警不会自动清零。字体换行使用保守字宽估计，不替代真实浏览器字形检查。未支持的范围应拆图或补材料，不删关系来使绘图成功。
