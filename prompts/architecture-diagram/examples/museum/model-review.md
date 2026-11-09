# 数字展览平台独立建模核对

## 读取范围与完成边界

业务建模输入仅为冻结提示词 `prompts/architecture-diagram/prompt.md` 和本目录 `input.md`，后者包括目标、读者、布局建议及 S1–S6。未读取其他模型、测试答案或其他会话。文件落位与执行边界规则仅用于约束文件操作，不用于补充架构事实。

目标是让集成开发人员核对分发中心与周边接口。完整保留八组、八节点、八关系；使用 radial 呈现建议。此轮仅为独立 AI 建模与自动化冒烟，不代替人类业务验收或浏览器验收。

## 实体与归属覆盖

| 材料 | 模块组 | 节点 | 类型 | 职责 | 结果 |
| --- | --- | --- | --- | --- | --- |
| S1、S2 | 分发 | 分发中心 | component | 分派展览资源请求 | 已覆盖 |
| S1、S2 | 策展 | 策展服务 | component | 维护展览条目 | 已覆盖 |
| S1、S2 | 存储 | 媒体库 | component | 存放媒体 | 已覆盖 |
| S1、S2 | 检索 | 检索服务 | component | 按关键词查询 | 已覆盖 |
| S1、S2 | 展厅终端 | 终端系统 | external_system | 播放资源 | 已覆盖 |
| S1、S2 | 语音 | 语音服务 | component | 生成解说 | 已覆盖 |
| S1、S2 | 统计 | 统计服务 | component | 汇总访问 | 已覆盖 |
| S1、S2 | 管理 | 管理台 | component | 调整发布配置 | 已覆盖 |

## 关系覆盖

| 材料 | 起点 → 终点 | 类型 | 标签 | 模型 ID |
| --- | --- | --- | --- | --- |
| S3 | 分发中心 → 策展服务 | calls | 查询条目 | r_query_entries |
| S3 | 分发中心 → 媒体库 | calls | 读取资源 | r_read_resources |
| S3 | 分发中心 → 检索服务 | calls | 查找内容 | r_find_content |
| S3 | 分发中心 → 语音服务 | calls | 生成解说 | r_generate_narration |
| S4 | 分发中心 → 终端系统 | data_flow | 展览资源 | r_send_resources |
| S4 | 分发中心 → 统计服务 | data_flow | 访问事件 | r_send_events |
| S5 | 管理台 → 分发中心 | calls | 更新配置 | r_update_configuration |
| S5 | 终端系统 → 分发中心 | feedback | 播放故障 | r_report_failure |

## 歧义、待确认项与未表达内容

- 材料明确实体类型、归属和关系方向，本模型没有推断项或未知候选关系，questions 为空。
- S1 未给出系统或部署边界，故 boundaries 为空、所有组 boundary 为 null。外部系统的类型不被扩写为未经提供的系统边界。
- S6 明确禁止假定部署方式，故没有 Kubernetes、消息队列、部署单元或部署关系。部署方式未知不影响本图接口范围；若要制作部署视图，需另补材料。
- S3 是调用关系，不能根据“读取资源”自行增加媒体库返回分发中心的数据流；未画的调用返回并非输入中已陈述而遗漏的关系。

## 真实建模困难

无阻塞性材料缺口。本次需要判断的是分发中心与终端系统之间有两条反向关系：资源下发与播放故障反馈具有不同含义，必须分别保留为两条 forward 关系，不能合并为单条 bidirectional 关系。第二个判断点是终端系统明确为 external_system，但没有边界定义，不能自行补“平台内部/外部”边界。

## 运行记录

1. `python3 tools/visual/renderers/architecture/validate.py prompts/architecture-diagram/examples/museum/model.json`：退出码 0，`valid: true`，`warnings: []`。
2. `python3 tools/visual/renderers/architecture/render.py --input prompts/architecture-diagram/examples/museum/model.json --output-dir outputs/uat-museum --theme white`：退出码 0，八节点、八组、八关系、实际渲染八关系，布局为 radial。
3. 四个约定产物均存在且非空：`diagram.svg`、`index.html`、`model.json`、`report.json`。SVG 可被 XML 解析器解析；导出模型与输入模型 JSON 内容一致。
4. 模型首次校验即通过，没有模型修正、没有修改提示词或引擎，没有提交或推送。

### 渲染器报告的全部告警

`edge-crossings` 报告四对交叉：

- `r_generate_narration` 与 `r_read_resources`：生成解说与读取资源。
- `r_generate_narration` 与 `r_send_resources`：生成解说与展览资源下发。
- `r_query_entries` 与 `r_update_configuration`：查询条目与更新配置。
- `r_read_resources` 与 `r_report_failure`：读取资源与播放故障反馈。

`edge-badge-in-ledger-only` 报告三项：

- `r_query_entries`
- `r_read_resources`
- `r_send_events`

含义按告警名称记录：上述三条关系的编号仅在关系清单中展示。渲染报告未列出共线告警。模型没有待确认项；人工语义验收状态仍是 `pending-human-review`，浏览器验收状态为 `not-assessed-by-renderer`。

### 结果与使用边界

独立 AI 建模和命令行冒烟成功；布局无交叉这一条件没有达到，不能把退出码 0 表述为图面通过。保留原图、全部关系与告警，不修改引擎，也不通过删除关系消除告警。是否属于影响可读性的严重交叉尚未目视确认。可考虑把“分发中心对资源服务的调用”与“终端、统计、管理接口及反馈”拆为两个视图，仍保留本模型作为总体关系清单；本轮未擅自替换要求的总体图。

本轮未进行浏览器目视检查或人类业务验收。SVG 解析及自动化检查不能证明箭头、文字、分组和缩放在浏览器中可读，也不能证明材料与业务真实一致。
