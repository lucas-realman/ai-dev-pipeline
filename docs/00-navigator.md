# AutoDev Pipeline — 文档架构导航

> **版本**: v2.2  
> **更新日期**: 2026-03-07  
> **原则**: 文档是最重要的资产，所有设计先于编码，文档驱动开发  
> **全局 ID 体系**: FR → SYS → ARCH → MOD → IF → DM → TC 全链路可追溯

---

## 文档体系总览

> ✅ = 已完成   ◻ = 规划中

```
docs/
├── 00-navigator.md                           ← 本文件，文档索引与阅读指南
│
├── 01-requirements/                          # ① 需求设计
│   └── ✅ REQ-001-系统需求规格说明书.md       #    23 FR + 15 NFR + 11 CON
│
├── 02-system-design/                         # ② 系统设计
│   └── ✅ SYS-001-系统设计说明书.md           #    上下文 + 四层架构 + 通信 + 6 ADR
│
├── 03-architecture/                          # ③ 架构设计
│   ├── ✅ ARCH-001-架构总览.md                #    风格 + 10 组件 + 数据流 + 选型
│   └── ✅ ARCH-002-部署架构.md                #    5 机拓扑 + 网络策略 + 容器化路线图
│
├── 04-outline-design/                        # ④ 概要设计
│   ├── ✅ OD-001-模块概要设计.md              #    索引页 → OD-SYS-001 + OD-MOD-001~013
│   ├── ✅ OD-SYS-001-系统概要设计.md          #    组件总览、分层架构、调用链、FR→MOD 映射
│   ├── ✅ OD-MOD-001~013                      #    13 模块概要设计 (每模块一文件)
│   ├── ✅ OD-002-数据模型设计.md              #    8 DM + 状态机 + 配置模型
│   └── ✅ OD-003-接口契约设计.md              #    12 内部接口 + 3 外部 API + 错误约定
│
├── 05-detail-design/                         # ⑤ 详细设计
│   ├── ✅ DD-001-详细设计说明书.md             #    索引页 → DD-SYS-001 + DD-MOD-001~013
│   ├── ✅ DD-SYS-001-系统详细设计.md          #    异常体系 + 日志规范 + LLM 抽象
│   └── ✅ DD-MOD-001~013                      #    13 模块详细设计 (31 ALG + 12 SEQ)
│
├── 06-traceability/                          # ⑥ 追溯矩阵
│   └── ✅ TRACE-001-追溯矩阵.md              #    FR→SYS→ARCH→MOD→IF→DM→TC 全链路
│
├── 07-testing/                               # ⑦ 测试设计
│   └── ✅ TEST-001-测试策略与方案.md          #    4 层测试 + 45 TC + 自动化执行
│
├── 08-iteration/                             # ⑧ 迭代计划
│   └── ✅ ITER-001-迭代计划.md               #    4 里程碑 + 5 Sprint 节奏
│
├── 09-operations/                            # ⑨ 运行与运维
│   └── ✅ OPS-003-风险识别与应对.md           #    7 项风险 + 应对策略
│
├── 10-references/                            # ⑩ 参考资料
│   └── ✅ REF-001-术语表.md                   #    10 术语 + 15 缩略语 + 编号体系
│
├── 11-archive/migrated/                      # ⑪ 迁移存档
│   ├── 03-硬件清单.md
│   ├── 05-测试方案与计划.md
│   ├── 08-自动化开发流水线.md                  #    v3.0 源文档 (3075 行)
│   ├── 09-测试机搭建计划.md
│   └── 10-风险识别与应对.md
│
├── 12-review/                                # ⑫ 评审纪要
│   ├── README.md                             #    评审流程 + 角色矩阵
│   ├── v1.0/                                 #    首次评审 (8 角色 + 总结)
│   │   ├── 01-CEO-评审意见.md
│   │   ├── 02-技术总监-评审意见.md
│   │   ├── 03-项目经理-评审意见.md
│   │   ├── 04-技术专家-评审意见.md
│   │   ├── 05-测试负责人-评审意见.md
│   │   ├── 06-质量负责人-评审意见.md
│   │   ├── 07-生产负责人-评审意见.md
│   │   ├── 08-产品负责人-评审意见.md
│   │   ├── 评审总结.md
│   │   └── ACTION-ITEMS.md               #    36 项行动项跟踪 (P0~P3)
│   ├── v2.0/                                 #    第二轮评审
│   ├── v2.1/                                 #    补充评审
│   ├── v3.0/                                 #    第三轮评审
│   └── v4.0/                                 #    第四轮评审 (31 项 ACTION-ITEMS)
```

---

## 已完成文档快速链接

| # | 文档 | 核心内容 | ID 范围 |
|---|------|---------|---------|
| 1 | [REQ-001](01-requirements/REQ-001-系统需求规格说明书.md) | 功能/非功能需求 + 约束 | FR-001~023, NFR-001~015, CON-001~011 |
| 2 | [SYS-001](02-system-design/SYS-001-系统设计说明书.md) | 系统上下文 + 四层模型 + ADR | SYS-001~009, ADR-001~006 |
| 3 | [ARCH-001](03-architecture/ARCH-001-架构总览.md) | 架构风格 + 组件 + 数据流 | ARCH-001~010 |
| 4 | [ARCH-002](03-architecture/ARCH-002-部署架构.md) | 物理拓扑 + 网络 + 容器化 | — |
| 5 | [OD-001](04-outline-design/OD-001-模块概要设计.md) | 索引页 → OD-SYS-001 + OD-MOD-001~013 | MOD-001~013, IF-001~012 |
| 6 | [OD-002](04-outline-design/OD-002-数据模型设计.md) | 数据模型 + 状态机 + 配置 | DM-001~008 |
| 7 | [OD-003](04-outline-design/OD-003-接口契约设计.md) | 接口签名 + 外部 API + 错误码 | IF-001~012 (详细契约) |
| 8 | [DD-001](05-detail-design/DD-001-详细设计说明书.md) | 索引页 → DD-SYS-001 + DD-MOD-001~013 | ALG-001~033, SEQ-001~012 |
| 9 | [TEST-001](07-testing/TEST-001-测试策略与方案.md) | 4 层测试 + 45 用例 + 自动化 | TC-001~127 |
| 10 | [TRACE-001](06-traceability/TRACE-001-追溯矩阵.md) | 全链路追溯 + 覆盖率 | 全部 ID 交叉引用 |
| 11 | [ITER-001](08-iteration/ITER-001-迭代计划.md) | 里程碑 + Sprint 节奏 | M0~M3 |
| 12 | [OPS-003](09-operations/OPS-003-风险识别与应对.md) | 风险登记 + 应对策略 | RISK-001~007 |
| 13 | [REF-001](10-references/REF-001-术语表.md) | 术语 + 缩略语 + 编号体系 | — |
| 14 | [评审纪要 v1.0](12-review/v1.0/评审总结.md) | 8 角色评审 + 36 行动项 + 综合评分 | A-001~036 |
| 15 | [评审纪要 v4.0](12-review/v4.0/ACTION-ITEMS.md) | 8角色+4技术专项, 31项发现, 3.4/5 | A-001~031 |

---

## 阅读顺序

### 快速了解（30 分钟）

1. **本文件** — 了解文档全貌
2. [REQ-001](01-requirements/REQ-001-系统需求规格说明书.md) — 系统要做什么
3. [ARCH-001](03-architecture/ARCH-001-架构总览.md) — 系统怎么做
4. [OD-001](04-outline-design/OD-001-模块概要设计.md) — 有哪些模块

### 深度理解（2 小时）

5. [SYS-001](02-system-design/SYS-001-系统设计说明书.md) — 系统设计全景
6. [OD-002](04-outline-design/OD-002-数据模型设计.md) + [OD-003](04-outline-design/OD-003-接口契约设计.md) — 数据结构与接口
7. [TEST-001](07-testing/TEST-001-测试策略与方案.md) — 质量保障体系

### 持续跟踪

8. [TRACE-001](06-traceability/TRACE-001-追溯矩阵.md) — 全链路追溯 & 覆盖率
9. [ITER-001](08-iteration/ITER-001-迭代计划.md) — 进度与里程碑

---

## 全局 ID 体系

| 命名空间 | 范围 | 定义文档 |
|----------|------|---------|
| FR-001 ~ FR-023 | 功能需求 | REQ-001 §2 |
| NFR-001 ~ NFR-015 | 非功能需求 | REQ-001 §3 |
| CON-001 ~ CON-011 | 约束 | REQ-001 §4 |
| SYS-001 ~ SYS-009 | 系统设计 | SYS-001 映射表 |
| ADR-001 ~ ADR-006 | 架构决策 | SYS-001 §4 |
| ARCH-001 ~ ARCH-010 | 架构组件 | ARCH-001 映射表 |
| MOD-001 ~ MOD-013 | 代码模块 | OD-001 映射表 |
| DM-001 ~ DM-008 | 数据模型 | OD-002 映射表 |
| IF-001 ~ IF-012 | 接口契约 | OD-001 §2.2 / OD-003 |
| TC-001 ~ TC-127 | 测试用例 | TEST-001 §2 |
| ALG-001 ~ ALG-033 | 算法描述 | DD-MOD-001~013 |
| SEQ-001 ~ SEQ-012 | 序列图 | DD-MOD-001~013 |
| RISK-001 ~ RISK-007 | 风险项 | OPS-003 §1 |

**追溯链**: FR → SYS → ARCH → MOD → IF/DM → TC

---

## 文档编号规范

| 前缀 | 含义 | 目录 | 示例 |
|------|------|------|------|
| `REQ-` | 需求文档 | 01-requirements/ | REQ-001 |
| `SYS-` | 系统设计 | 02-system-design/ | SYS-001 |
| `ARCH-` | 架构设计 | 03-architecture/ | ARCH-001, ARCH-002 |
| `OD-` | 概要设计 | 04-outline-design/ | OD-001, OD-SYS-001, OD-MOD-001~013 |
| `DD-` | 详细设计 | 05-detail-design/ | DD-001, DD-SYS-001, DD-MOD-001~013 |
| `TRACE-` | 追溯矩阵 | 06-traceability/ | TRACE-001 |
| `TEST-` | 测试设计 | 07-testing/ | TEST-001 |
| `ITER-` | 迭代计划 | 08-iteration/ | ITER-001 |
| `OPS-` | 运维风险 | 09-operations/ | OPS-003 |
| `REF-` | 参考资料 | 10-references/ | REF-001 |
| `RV-` | 评审纪要 | 12-review/ | v1.0/ |

---

## 文档与代码的关系

```
docs/01-requirements/   →  定义「做什么」          →  FR-001~023
docs/02-system-design/  →  定义「怎么做」(宏观)     →  SYS-001~009 + ADR-001~006
docs/03-architecture/   →  定义「用什么架构」       →  ARCH-001~010
docs/04-outline-design/ →  定义「模块怎么划分」     →  MOD-001~013 → orchestrator/*.py
docs/05-detail-design/  →  定义「模块怎么实现」     →  DD-MOD-001~013
docs/06-traceability/   →  追踪「设计 = 实现?」     →  全 ID 交叉引用
docs/07-testing/        →  定义「怎么验证」         →  TC-001~127 → tests/*.py
docs/08-iteration/      →  规划「节奏与里程碑」
docs/09-operations/     →  管理「风险与运维」
docs/10-references/     →  统一「术语与编号」
```

---

## 版本管理规则

- 每个文档头部必须有 `版本` + `更新日期`
- 重大变更在文档头部追加 `vX.Y 变更:` 行
- 文档随代码一起 commit, 同一 PR/sprint 内保持一致
- 自动生成的文档 (sprint report 等) 放在 `08-iteration/sprints/` 和 `reports/`
