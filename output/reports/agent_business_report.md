# Final Business Report

业务问题：Why did Product GMV decline, and what were the main drivers?

分析状态：已验证确定性分析示例；不是未完成 LLM Demo 的输出；来源：existing deterministic SQL/Python analysis artifacts

报告模式：deterministic

报告仅呈现输入证据；生成成功不等于分析任务已完成。数值保持输入精度，百分数单位以字段名为准。

## Executive Summary

- **Product GMV 异动**：previous\_month=2017-11；current\_month=2017-12；gmv\_change=-266357.2；gmv\_mom\_pct=-26.364916190785447。[gmv]

- **GMV Change → Order Volume Contribution**：volume\_effect=-244693.41597392978；volume\_contribution\_pct=91.86664222852987。[volume]

- **GMV Change → AOV Contribution**：aov\_effect=-21663.784026070167；aov\_contribution\_pct=8.133357771470104。[aov_effect]

- **主要算术驱动（不等于因果）**：main\_driver=Order Volume。[driver]

- **最大下降贡献：product\_category**：member=cama\_mesa\_banho；absolute\_change=-38906.69；contribution\_to\_total\_decline\_pct=14.606960127227648。[top_product_category]

- **最大下降贡献：customer\_state**：member=SP；absolute\_change=-79511.75；contribution\_to\_total\_decline\_pct=29.85154897258268。[top_customer_state]

- **最大下降贡献：seller**：member=7e93a43ef30c4f03f38b393420bc753a；absolute\_change=-19384.78；contribution\_to\_total\_decline\_pct=7.277738315314923。[top_seller]

## Anomaly Overview

### Product GMV 异动 [gmv]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| previous\_month | 2017-11 |
| current\_month | 2017-12 |
| previous\_gmv | 1010271.37 |
| current\_gmv | 743914.17 |
| gmv\_change | -266357.2 |
| gmv\_mom\_pct | -26.364916190785447 |

### 可比较性与异常状态 [period]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| anomaly\_status | True |
| comparable\_months | 2017-02, 2017-03, 2017-04, 2017-05, 2017-06, 2017-07, 2017-08, 2017-09, 2017-10, 2017-11, 2017-12, 2018-01, 2018-02, 2018-03, 2018-04, 2018-05, 2018-06, 2018-07 |

### Order Volume（有效明细订单） [orders]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| previous\_orders | 7451 |
| current\_orders | 5624 |
| order\_mom\_pct | -24.520198631056232 |

### AOV [aov]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| previous\_aov | 135.58869547711717 |
| current\_aov | 132.27492354196303 |
| aov\_mom\_pct | -2.443988360160443 |

### 订单量与 AOV 绝对变化 [changes]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| order\_change | -1827 |
| aov\_change | -3.3137719351541364 |

## Metric Decomposition

### GMV Change → Order Volume Contribution [volume]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| volume\_effect | -244693.41597392978 |
| volume\_contribution\_pct | 91.86664222852987 |

### GMV Change → AOV Contribution [aov_effect]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| aov\_effect | -21663.784026070167 |
| aov\_contribution\_pct | 8.133357771470104 |

### 主要算术驱动（不等于因果） [driver]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| main\_driver | Order Volume |

## Dimension Attribution

### 最大下降贡献：product\_category [top_product_category]

期间：2017-11 → 2017-12；维度/路径：product\_category

| 字段 | 值 |
|---|---:|
| member | cama\_mesa\_banho |
| previous\_gmv | 89412.54 |
| current\_gmv | 50505.85 |
| absolute\_change | -38906.69 |
| growth\_rate\_pct | -43.51368387476745 |
| contribution\_to\_total\_decline\_pct | 14.606960127227648 |

### 最大下降贡献：customer\_state [top_customer_state]

期间：2017-11 → 2017-12；维度/路径：customer\_state

| 字段 | 值 |
|---|---:|
| member | SP |
| previous\_gmv | 360251.89 |
| current\_gmv | 280740.14 |
| absolute\_change | -79511.75 |
| growth\_rate\_pct | -22.071154158275196 |
| contribution\_to\_total\_decline\_pct | 29.85154897258268 |

### 最大下降贡献：seller [top_seller]

期间：2017-11 → 2017-12；维度/路径：seller

| 字段 | 值 |
|---|---:|
| member | 7e93a43ef30c4f03f38b393420bc753a |
| previous\_gmv | 20075.76 |
| current\_gmv | 690.98 |
| absolute\_change | -19384.78 |
| growth\_rate\_pct | -96.55813777411166 |
| contribution\_to\_total\_decline\_pct | 7.277738315314923 |

## Drill-down Findings

### 下钻：product\_category [drill_product_category]

期间：2017-11 → 2017-12；维度/路径：Overall GMV → customer\_state → SP → product\_category

| 字段 | 值 |
|---|---:|
| parent\_dimension | customer\_state |
| parent\_member | SP |
| member | cama\_mesa\_banho |
| previous\_gmv | 37541.65 |
| current\_gmv | 23143.7 |
| absolute\_change | -14397.95 |
| contribution\_to\_parent\_decline\_pct | 18.107952598200892 |

### 下钻：seller [drill_seller]

期间：2017-11 → 2017-12；维度/路径：Overall GMV → customer\_state → SP → seller

| 字段 | 值 |
|---|---:|
| parent\_dimension | customer\_state |
| parent\_member | SP |
| member | 7e93a43ef30c4f03f38b393420bc753a |
| previous\_gmv | 8434.87 |
| current\_gmv | 379.0 |
| absolute\_change | -8055.87 |
| contribution\_to\_parent\_decline\_pct | 10.131672362889761 |

## Evidence

### Product GMV 异动 [gmv]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| previous\_month | 2017-11 |
| current\_month | 2017-12 |
| previous\_gmv | 1010271.37 |
| current\_gmv | 743914.17 |
| gmv\_change | -266357.2 |
| gmv\_mom\_pct | -26.364916190785447 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"previous\_month": \["previous\_month"\], "current\_month": \["current\_month"\], "previous\_gmv": \["previous\_gmv"\], "current\_gmv": \["current\_gmv"\], "gmv\_change": \["gmv\_change"\], "gmv\_mom\_pct": \["gmv\_mom\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

### 可比较性与异常状态 [period]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| anomaly\_status | True |
| comparable\_months | 2017-02, 2017-03, 2017-04, 2017-05, 2017-06, 2017-07, 2017-08, 2017-09, 2017-10, 2017-11, 2017-12, 2018-01, 2018-02, 2018-03, 2018-04, 2018-05, 2018-06, 2018-07 |

来源：deterministic\_python / scripts/demo\_business\_report.py::example\_bundle

字段引用：\{"anomaly\_status": \["anomaly\_status"\], "comparable\_months": \["comparable\_months"\]\}

SQL/计算引用：change=current-previous; main\_driver=argmax\(abs\(volume\_effect\),abs\(aov\_effect\)\); anomaly=current\_month in candidate\_months; comparable\_months=join\(existing list\)

### Order Volume（有效明细订单） [orders]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| previous\_orders | 7451 |
| current\_orders | 5624 |
| order\_mom\_pct | -24.520198631056232 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"previous\_orders": \["previous\_orders"\], "current\_orders": \["current\_orders"\], "order\_mom\_pct": \["order\_mom\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

### AOV [aov]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| previous\_aov | 135.58869547711717 |
| current\_aov | 132.27492354196303 |
| aov\_mom\_pct | -2.443988360160443 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"previous\_aov": \["previous\_aov"\], "current\_aov": \["current\_aov"\], "aov\_mom\_pct": \["aov\_mom\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

### 订单量与 AOV 绝对变化 [changes]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| order\_change | -1827 |
| aov\_change | -3.3137719351541364 |

来源：deterministic\_python / scripts/demo\_business\_report.py::example\_bundle

字段引用：\{"order\_change": \["order\_change"\], "aov\_change": \["aov\_change"\]\}

SQL/计算引用：change=current-previous; main\_driver=argmax\(abs\(volume\_effect\),abs\(aov\_effect\)\); anomaly=current\_month in candidate\_months; comparable\_months=join\(existing list\)

### GMV Change → Order Volume Contribution [volume]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| volume\_effect | -244693.41597392978 |
| volume\_contribution\_pct | 91.86664222852987 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"volume\_effect": \["volume\_effect"\], "volume\_contribution\_pct": \["volume\_contribution\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

### GMV Change → AOV Contribution [aov_effect]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| aov\_effect | -21663.784026070167 |
| aov\_contribution\_pct | 8.133357771470104 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"aov\_effect": \["aov\_effect"\], "aov\_contribution\_pct": \["aov\_contribution\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

### 主要算术驱动（不等于因果） [driver]

期间：2017-11 → 2017-12；维度/路径：Overall

| 字段 | 值 |
|---|---:|
| main\_driver | Order Volume |

来源：deterministic\_python / scripts/demo\_business\_report.py::example\_bundle

字段引用：\{"main\_driver": \["main\_driver"\]\}

SQL/计算引用：change=current-previous; main\_driver=argmax\(abs\(volume\_effect\),abs\(aov\_effect\)\); anomaly=current\_month in candidate\_months; comparable\_months=join\(existing list\)

### 最大下降贡献：product\_category [top_product_category]

期间：2017-11 → 2017-12；维度/路径：product\_category

| 字段 | 值 |
|---|---:|
| member | cama\_mesa\_banho |
| previous\_gmv | 89412.54 |
| current\_gmv | 50505.85 |
| absolute\_change | -38906.69 |
| growth\_rate\_pct | -43.51368387476745 |
| contribution\_to\_total\_decline\_pct | 14.606960127227648 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"member": \["top\_dimensions", "product\_category", "member"\], "previous\_gmv": \["top\_dimensions", "product\_category", "previous\_gmv"\], "current\_gmv": \["top\_dimensions", "product\_category", "current\_gmv"\], "absolute\_change": \["top\_dimensions", "product\_category", "absolute\_change"\], "growth\_rate\_pct": \["top\_dimensions", "product\_category", "growth\_rate\_pct"\], "contribution\_to\_total\_decline\_pct": \["top\_dimensions", "product\_category", "contribution\_to\_total\_decline\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

### 最大下降贡献：customer\_state [top_customer_state]

期间：2017-11 → 2017-12；维度/路径：customer\_state

| 字段 | 值 |
|---|---:|
| member | SP |
| previous\_gmv | 360251.89 |
| current\_gmv | 280740.14 |
| absolute\_change | -79511.75 |
| growth\_rate\_pct | -22.071154158275196 |
| contribution\_to\_total\_decline\_pct | 29.85154897258268 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"member": \["top\_dimensions", "customer\_state", "member"\], "previous\_gmv": \["top\_dimensions", "customer\_state", "previous\_gmv"\], "current\_gmv": \["top\_dimensions", "customer\_state", "current\_gmv"\], "absolute\_change": \["top\_dimensions", "customer\_state", "absolute\_change"\], "growth\_rate\_pct": \["top\_dimensions", "customer\_state", "growth\_rate\_pct"\], "contribution\_to\_total\_decline\_pct": \["top\_dimensions", "customer\_state", "contribution\_to\_total\_decline\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

### 最大下降贡献：seller [top_seller]

期间：2017-11 → 2017-12；维度/路径：seller

| 字段 | 值 |
|---|---:|
| member | 7e93a43ef30c4f03f38b393420bc753a |
| previous\_gmv | 20075.76 |
| current\_gmv | 690.98 |
| absolute\_change | -19384.78 |
| growth\_rate\_pct | -96.55813777411166 |
| contribution\_to\_total\_decline\_pct | 7.277738315314923 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"member": \["top\_dimensions", "seller", "member"\], "previous\_gmv": \["top\_dimensions", "seller", "previous\_gmv"\], "current\_gmv": \["top\_dimensions", "seller", "current\_gmv"\], "absolute\_change": \["top\_dimensions", "seller", "absolute\_change"\], "growth\_rate\_pct": \["top\_dimensions", "seller", "growth\_rate\_pct"\], "contribution\_to\_total\_decline\_pct": \["top\_dimensions", "seller", "contribution\_to\_total\_decline\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

### 下钻：product\_category [drill_product_category]

期间：2017-11 → 2017-12；维度/路径：Overall GMV → customer\_state → SP → product\_category

| 字段 | 值 |
|---|---:|
| parent\_dimension | customer\_state |
| parent\_member | SP |
| member | cama\_mesa\_banho |
| previous\_gmv | 37541.65 |
| current\_gmv | 23143.7 |
| absolute\_change | -14397.95 |
| contribution\_to\_parent\_decline\_pct | 18.107952598200892 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"parent\_dimension": \["drill\_top", "product\_category", "parent\_dimension"\], "parent\_member": \["drill\_top", "product\_category", "parent\_member"\], "member": \["drill\_top", "product\_category", "member"\], "previous\_gmv": \["drill\_top", "product\_category", "previous\_gmv"\], "current\_gmv": \["drill\_top", "product\_category", "current\_gmv"\], "absolute\_change": \["drill\_top", "product\_category", "absolute\_change"\], "contribution\_to\_parent\_decline\_pct": \["drill\_top", "product\_category", "contribution\_to\_parent\_decline\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

### 下钻：seller [drill_seller]

期间：2017-11 → 2017-12；维度/路径：Overall GMV → customer\_state → SP → seller

| 字段 | 值 |
|---|---:|
| parent\_dimension | customer\_state |
| parent\_member | SP |
| member | 7e93a43ef30c4f03f38b393420bc753a |
| previous\_gmv | 8434.87 |
| current\_gmv | 379.0 |
| absolute\_change | -8055.87 |
| contribution\_to\_parent\_decline\_pct | 10.131672362889761 |

来源：deterministic\_python / output/reports/gmv\_ground\_truth\_summary.json

字段引用：\{"parent\_dimension": \["drill\_top", "seller", "parent\_dimension"\], "parent\_member": \["drill\_top", "seller", "parent\_member"\], "member": \["drill\_top", "seller", "member"\], "previous\_gmv": \["drill\_top", "seller", "previous\_gmv"\], "current\_gmv": \["drill\_top", "seller", "current\_gmv"\], "absolute\_change": \["drill\_top", "seller", "absolute\_change"\], "contribution\_to\_parent\_decline\_pct": \["drill\_top", "seller", "contribution\_to\_parent\_decline\_pct"\]\}

SQL/计算引用：scripts/gmv\_ground\_truth.py；SQL清单 output/reports/gmv\_ground\_truth\_queries.json

## Hypotheses（待验证）

以下均为待验证解释，不属于 Evidence；报告生成器不能自动验证因果关系。

- 访问量或转化率下降可能影响订单量，需要漏斗数据验证。

- 前期促销拉高基数或活动变化可能影响比较，需要活动日历验证；当前交易数据不能确认。

- 库存或卖家可售状态变化可能影响供给，需要库存和商家日志验证。

## Limitations

- 每日有订单仅是期间可比较性的代理，不能证明抽取完整。

- Product GMV 不含运费、不扣退款，保留所有状态的有效明细订单，不等于收入。

- 指标分解是算术归因，维度贡献是描述性定位；不同维度不能相加或解释为因果。

- 自然月天数、季节性与订单状态快照影响业务解释。

- 来源字段一致性已经校验；标签、口径和事实语义仍依赖上游分析及人工复核。

## Recommended Next Checks（不是已验证结论）

- 检查访问量、转化率与渠道漏斗。

- 核对活动日历与折扣变化。

- 检查重点地区相关品类的库存与缺货记录。

- 复核下降贡献较大卖家的可售状态、商品供给与运营日志。
