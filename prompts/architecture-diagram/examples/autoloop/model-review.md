# Autoloop 独立建模核对

## 实际读取范围与独立性

建模资料只读取冻结的 `prompts/architecture-diagram/prompt.md` 和本例 `input.md`。未读其他模型、测试答案或其他会话。另读全局执行与文件落位规则，仅用于操作约束，不作为系统架构依据。输入是虚构测试材料，目标读者为平台开发人员；本模型解释控制调用、执行数据返回和质量反馈。

## 材料覆盖表

| 材料 | 实体或关系 | 模型覆盖 |
|---|---|---|
| S1 | 自动任务平台系统边界 | b_platform |
| S1 | 任务接入、执行、质量反馈三组及同一系统归属 | g_intake、g_execution、g_quality |
| S2 | 任务 API、计划器及职责和组归属 | n_api、n_planner |
| S2 | 工作器、工具适配器及职责和组归属 | n_worker、n_adapter |
| S2 | 检查器、结果库及职责和组归属；六项均为组件 | n_checker、n_store；所有节点 kind=component |
| S3 | API 调用计划器 | r_api_planner，calls，API → 计划器 |
| S3 | 计划器调用工作器 | r_planner_worker，calls，计划器 → 工作器 |
| S3 | 工作器调用工具适配器 | r_worker_adapter，calls，工作器 → 工具适配器 |
| S4 | 工具适配器向工作器返回执行数据 | r_adapter_worker，data_flow，工具适配器 → 工作器 |
| S4 | 工作器传结果给检查器 | r_worker_checker，data_flow，工作器 → 检查器 |
| S4 | 检查器传记录给结果库 | r_checker_store，data_flow，检查器 → 结果库 |
| S5 | 检查器反馈失败原因给计划器 | r_checker_planner，feedback，检查器 → 计划器 |
| S5 | 结果库提供已完成结果给 API | r_store_api，data_flow，结果库 → API |
| S6 | 虚构实现、未给认证机制且禁止补画 | description 限定范围；未增加认证组件 |

## 歧义、未表达内容与待确认项

材料明示的实体与关系均已覆盖，无需对已建模内容引入推断或未知项，questions 为空。S2 的“受控工具”只用于说明工具适配器职责，未给出可识别的具体工具实体与边界，因此不额外建节点；S3–S5 的全部显式端点与八条关系完整保留。未补充认证、部署、调用协议、失败重试策略、API 主动查询等材料未说明的细节。若需要表现这些细节，应新增输入后建模，不作为本图已知事实。

## 建模时实际需要判断的地方

工作器调用适配器与适配器返回数据具有相反方向但不同语义，必须保留为两条单向关系，不能合并成无区别的双向调用。结果库提供结果只支持结果库到 API 的数据流，不能自动补一条 API 发起查询。失败原因到计划器是明确反馈，不能因形成回环省略。除此之外，原始材料的组、类型和职责足够明确，未遇到信息缺失阻止建模的问题。

## 执行与验收边界

本次仅为独立 AI 建模与命令行冒烟，不能替代人类业务验收或浏览器验收。后续追加实际命令结果、检查器报告及失败记录。

### 实际运行结果

`validate.py` 首次执行通过：`valid=true`，`warnings=[]`。`render.py` 首次执行退出码为 0，生成 diagram.svg、index.html、model.json、report.json；四个文件均非空，导出 model.json 与输入解析后的对象完全一致。模型含 1 个边界、3 个组、6 个组件、8 条关系、0 个待确认项；导出关系 8 条。未发生合同校验失败，未修订模型，未修改提示词或引擎。

导出布局为 layered。自动检查报 6 对交叉、2 对共享线段，且 8 条关系均有 edge-badge-in-ledger-only 提示。以下为原样报告，不按退出码零掩盖布局警告：

```json
{
  "version": "0.1.0-draft",
  "model_sha256": "22b66a9d797ab7510c34695c14df4dc19cb814d1210bf90fa001925c9b6e3482",
  "nodes": 6,
  "groups": 3,
  "relations": 8,
  "rendered_relations": 8,
  "layout_modes": [
    "layered"
  ],
  "warnings": [
    {
      "code": "edge-crossings",
      "pairs": [
        [
          "r_adapter_worker",
          "r_worker_adapter"
        ],
        [
          "r_checker_planner",
          "r_checker_store"
        ],
        [
          "r_checker_store",
          "r_store_api"
        ],
        [
          "r_planner_worker",
          "r_worker_checker"
        ],
        [
          "r_store_api",
          "r_worker_checker"
        ],
        [
          "r_worker_adapter",
          "r_worker_checker"
        ]
      ]
    },
    {
      "code": "shared-edge-segments",
      "pairs": [
        [
          "r_adapter_worker",
          "r_planner_worker"
        ],
        [
          "r_api_planner",
          "r_checker_planner"
        ]
      ]
    },
    {
      "code": "edge-badge-in-ledger-only",
      "id": "r_adapter_worker"
    },
    {
      "code": "edge-badge-in-ledger-only",
      "id": "r_api_planner"
    },
    {
      "code": "edge-badge-in-ledger-only",
      "id": "r_checker_planner"
    },
    {
      "code": "edge-badge-in-ledger-only",
      "id": "r_checker_store"
    },
    {
      "code": "edge-badge-in-ledger-only",
      "id": "r_planner_worker"
    },
    {
      "code": "edge-badge-in-ledger-only",
      "id": "r_store_api"
    },
    {
      "code": "edge-badge-in-ledger-only",
      "id": "r_worker_adapter"
    },
    {
      "code": "edge-badge-in-ledger-only",
      "id": "r_worker_checker"
    }
  ],
  "semantic_acceptance": "pending-human-review",
  "browser_acceptance": "not-assessed-by-renderer",
  "geometry": {
    "nodes": {
      "n_adapter": {
        "x": 110,
        "y": 250,
        "w": 260,
        "h": 91,
        "lines": [
          "工具适配器"
        ],
        "body": [
          "调用受控工具"
        ]
      },
      "n_worker": {
        "x": 110,
        "y": 377,
        "w": 260,
        "h": 91,
        "lines": [
          "工作器"
        ],
        "body": [
          "执行步骤"
        ]
      },
      "n_api": {
        "x": 110,
        "y": 702,
        "w": 260,
        "h": 91,
        "lines": [
          "任务 API"
        ],
        "body": [
          "接收任务请求"
        ]
      },
      "n_planner": {
        "x": 110,
        "y": 829,
        "w": 260,
        "h": 91,
        "lines": [
          "计划器"
        ],
        "body": [
          "拆解并调度任务"
        ]
      },
      "n_checker": {
        "x": 110,
        "y": 1154,
        "w": 260,
        "h": 91,
        "lines": [
          "检查器"
        ],
        "body": [
          "核对执行结果"
        ]
      },
      "n_store": {
        "x": 110,
        "y": 1281,
        "w": 260,
        "h": 91,
        "lines": [
          "结果库"
        ],
        "body": [
          "存储检查记录"
        ]
      }
    },
    "groups": {
      "g_execution": {
        "x": 80,
        "y": 180,
        "w": 320,
        "h": 332,
        "header_h": 58,
        "lines": [
          "执行"
        ]
      },
      "g_intake": {
        "x": 80,
        "y": 632,
        "w": 320,
        "h": 332,
        "header_h": 58,
        "lines": [
          "任务接入"
        ]
      },
      "g_quality": {
        "x": 80,
        "y": 1084,
        "w": 320,
        "h": 332,
        "header_h": 58,
        "lines": [
          "质量反馈"
        ]
      }
    },
    "boundaries": {
      "b_platform": {
        "x": 52,
        "y": 100,
        "w": 376,
        "h": 1344
      }
    },
    "routes": {
      "r_adapter_worker": {
        "points": [
          [
            370,
            295.5
          ],
          [
            392,
            295.5
          ],
          [
            392,
            365
          ],
          [
            88,
            365
          ],
          [
            88,
            422.5
          ],
          [
            110,
            422.5
          ]
        ],
        "number": 1,
        "badge": null
      },
      "r_api_planner": {
        "points": [
          [
            370,
            747.5
          ],
          [
            392,
            747.5
          ],
          [
            392,
            817
          ],
          [
            88,
            817
          ],
          [
            88,
            874.5
          ],
          [
            110,
            874.5
          ]
        ],
        "number": 2,
        "badge": null
      },
      "r_checker_planner": {
        "points": [
          [
            370,
            1199.5
          ],
          [
            412,
            1199.5
          ],
          [
            412,
            932
          ],
          [
            88,
            932
          ],
          [
            88,
            866.5
          ],
          [
            110,
            866.5
          ]
        ],
        "number": 3,
        "badge": null
      },
      "r_checker_store": {
        "points": [
          [
            370,
            1191.5
          ],
          [
            392,
            1191.5
          ],
          [
            392,
            1269
          ],
          [
            88,
            1269
          ],
          [
            88,
            1326.5
          ],
          [
            110,
            1326.5
          ]
        ],
        "number": 4,
        "badge": null
      },
      "r_planner_worker": {
        "points": [
          [
            370,
            874.5
          ],
          [
            412,
            874.5
          ],
          [
            412,
            480
          ],
          [
            88,
            480
          ],
          [
            88,
            414.5
          ],
          [
            110,
            414.5
          ]
        ],
        "number": 5,
        "badge": null
      },
      "r_store_api": {
        "points": [
          [
            370,
            1326.5
          ],
          [
            382,
            1326.5
          ],
          [
            382,
            1257
          ],
          [
            68,
            1257
          ],
          [
            68,
            747.5
          ],
          [
            110,
            747.5
          ]
        ],
        "number": 6,
        "badge": null
      },
      "r_worker_adapter": {
        "points": [
          [
            370,
            422.5
          ],
          [
            382,
            422.5
          ],
          [
            382,
            353
          ],
          [
            88,
            353
          ],
          [
            88,
            295.5
          ],
          [
            110,
            295.5
          ]
        ],
        "number": 7,
        "badge": null
      },
      "r_worker_checker": {
        "points": [
          [
            370,
            414.5
          ],
          [
            392,
            414.5
          ],
          [
            392,
            620
          ],
          [
            40,
            620
          ],
          [
            40,
            1199.5
          ],
          [
            110,
            1199.5
          ]
        ],
        "number": 8,
        "badge": null
      }
    },
    "width": 508,
    "height": 1504,
    "modes": [
      "layered"
    ],
    "warnings": [
      {
        "code": "edge-crossings",
        "pairs": [
          [
            "r_adapter_worker",
            "r_worker_adapter"
          ],
          [
            "r_checker_planner",
            "r_checker_store"
          ],
          [
            "r_checker_store",
            "r_store_api"
          ],
          [
            "r_planner_worker",
            "r_worker_checker"
          ],
          [
            "r_store_api",
            "r_worker_checker"
          ],
          [
            "r_worker_adapter",
            "r_worker_checker"
          ]
        ]
      },
      {
        "code": "shared-edge-segments",
        "pairs": [
          [
            "r_adapter_worker",
            "r_planner_worker"
          ],
          [
            "r_api_planner",
            "r_checker_planner"
          ]
        ]
      },
      {
        "code": "edge-badge-in-ledger-only",
        "id": "r_adapter_worker"
      },
      {
        "code": "edge-badge-in-ledger-only",
        "id": "r_api_planner"
      },
      {
        "code": "edge-badge-in-ledger-only",
        "id": "r_checker_planner"
      },
      {
        "code": "edge-badge-in-ledger-only",
        "id": "r_checker_store"
      },
      {
        "code": "edge-badge-in-ledger-only",
        "id": "r_planner_worker"
      },
      {
        "code": "edge-badge-in-ledger-only",
        "id": "r_store_api"
      },
      {
        "code": "edge-badge-in-ledger-only",
        "id": "r_worker_adapter"
      },
      {
        "code": "edge-badge-in-ledger-only",
        "id": "r_worker_checker"
      }
    ]
  }
}
```

这些结果说明结构与导出冒烟完成，但布局可读性未通过人工或浏览器判断。建议保留本图作为完整关系总览，并在需要降低交叉时另拆“控制与执行数据返回”视图（r_api_planner、r_planner_worker、r_worker_adapter、r_adapter_worker）和“质量与结果反馈”视图（r_worker_checker、r_checker_store、r_checker_planner、r_store_api）；两图共享组件标识，保留本模型作为完整关系清单。本轮不改引擎、不删关系、不把建议拆图称为已执行。

未进行浏览器目视验收、人类业务语义验收或真实平台实现核实；本次结论仅限独立 AI 建模与自动化冒烟。
