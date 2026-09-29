# Tableau Dashboard 数据说明

仅对已有 Ground Truth 输出做字段映射、日期格式和百分数转小数；未重算原始交易数据，未修改指标或源报告。用户已在 Tableau 2025.1 中完成 Dashboard 搭建与验证，本地原件为 `BusinessInsight_Dashboard.twb`，保留原样且不提交 GitHub。分析结果和 Tableau-ready 数据由 Agent / deterministic analysis 提供，Dashboard 由用户使用 Tableau 构建，并非 Agent 自动生成。

## GitHub 公开副本

[BusinessInsight_Dashboard_public.twb](BusinessInsight_Dashboard_public.twb) 约 441 KB，仅将原件五处本机绝对连接目录改为 `.`，保留其他 XML、图表和数据源设置。与本目录五张 CSV 一起下载；公开副本已通过 XML 差异与引用检查，尚未在另一台机器的 Tableau UI 中验证。如提示缺少数据源，使用 Tableau 重新定位同目录相应 CSV。此副本不是新 Dashboard，不替换本地已验证原件。数据归属及许可见 [DATA_NOTICE.md](../../DATA_NOTICE.md)。

## 图表对应

| 文件 | 建议图表 | 粒度 |
|---|---|---|
| monthly_metrics_tableau.csv | GMV 月度趋势、订单量/AOV 趋势、异常月份标记 | 每自然月一行，保留不可比较月供质量检查 |
| category_contribution_tableau.csv | 品类下降贡献条形图、上期/当期对比 | 每品类一行 |
| state_contribution_tableau.csv | 客户州贡献条形图 | 每客户州一行 |
| seller_contribution_tableau.csv | 卖家下降贡献 Top N 条形图 | 每 seller_id 一行 |
| sp_drilldown_tableau.csv | SP 内品类/卖家下钻图 | dimension_type + member 一行 |

## 口径与格式

- 主案例：2017-11 → 2017-12。GMV=商品 price 总额，不含运费；订单量为有有效明细的去重订单；AOV=GMV/订单量。保持所有状态的有效明细订单口径。
- month 为 YYYY-MM-DD（月首日），例如 2017-12-01；导入后检查为 Date。布尔字段为 true/false；金额、AOV 和比例为无千分位符的数字，order_volume 为整数。CSV 为 UTF-8、逗号分隔、首行为字段名。
- rate 与 mom 均为小数，可在 Tableau 设置百分比显示。源报告的 *_pct 除以 100，不额外舍入。
- is_comparable 继承报告：订单与有效明细每天均有记录。is_anomaly 为 is_comparable=true 且已有有效 GMV MoM <= -0.10。首个可比较月若无合格前月，MoM 为空，不能标为异常。
- 维度缺失统一 Unknown；数值未定义（零基期增长率、不可比较 MoM、无订单 AOV）保留空值/Null，不写 Unknown 或伪造 0，以保持 numeric 类型。
- category/state/seller 的 contribution_rate 分母为总体净 GMV 变化 -266357.20。
- SP 下钻 contribution_rate 使用源报告 contribution_to_parent_decline_pct，分母为 SP 净 GMV 变化 -79511.75；不是总体下降。category 与 seller 是两种视角，必须先按 dimension_type 筛选，不能合并相加。
- 总体下降时下降组贡献为正，增长组为负；贡献可超过 100%。保留新增、消失与 Unknown 成员，不只输出 Top N。
- 五个文件建议分别作为数据源，避免跨粒度 JOIN 或将平行贡献视角 UNION 后求和。趋势图筛选 is_comparable=true；不要对月度 AOV/MoM 跨月求和。Top N 仅作展示，分母仍为完整总体，不能用可见 Top N 重新计算贡献率。
- seller_id/member/category/state 设为字符串维度。SP 是巴西客户州代码；若制作地图，需要在 Tableau 明确国家为 Brazil 并核对地理匹配，本文件不包含坐标。

## 来源

- ../reports/monthly_metrics.csv
- ../reports/dimension_contribution.csv
- ../reports/gmv_drill_down.csv
- ../reports/gmv_ground_truth_summary.json

## 导出校验

已逐文件回读：校验日期、布尔、整数/小数可解析性、行数、维度键唯一性和空值；源文件 SHA-256 前后相同。以下空值为源结果中有意保留的未定义数值，其他字段无缺失。

### monthly_metrics_tableau.csv

行数：26。

| 字段 | 类型 | 空值数 |
|---|---|---:|
| month | Date | 0 |
| gmv | Decimal | 0 |
| gmv_mom | Decimal | 9 |
| order_volume | Integer | 0 |
| order_volume_mom | Decimal | 9 |
| aov | Decimal | 2 |
| aov_mom | Decimal | 9 |
| is_comparable | Boolean | 0 |
| is_anomaly | Boolean | 0 |

### category_contribution_tableau.csv

行数：67。

| 字段 | 类型 | 空值数 |
|---|---|---:|
| category | String | 0 |
| previous_gmv | Decimal | 0 |
| current_gmv | Decimal | 0 |
| absolute_change | Decimal | 0 |
| growth_rate | Decimal | 1 |
| contribution_rate | Decimal | 0 |

### state_contribution_tableau.csv

行数：27。

| 字段 | 类型 | 空值数 |
|---|---|---:|
| state | String | 0 |
| previous_gmv | Decimal | 0 |
| current_gmv | Decimal | 0 |
| absolute_change | Decimal | 0 |
| growth_rate | Decimal | 0 |
| contribution_rate | Decimal | 0 |

### seller_contribution_tableau.csv

行数：1157。

| 字段 | 类型 | 空值数 |
|---|---|---:|
| seller_id | String | 0 |
| previous_gmv | Decimal | 0 |
| current_gmv | Decimal | 0 |
| absolute_change | Decimal | 0 |
| growth_rate | Decimal | 192 |
| contribution_rate | Decimal | 0 |

### sp_drilldown_tableau.csv

行数：919。

| 字段 | 类型 | 空值数 |
|---|---|---:|
| dimension_type | String | 0 |
| member | String | 0 |
| previous_gmv | Decimal | 0 |
| current_gmv | Decimal | 0 |
| absolute_change | Decimal | 0 |
| contribution_rate | Decimal | 0 |

## 金额对账

| 分组视角 | absolute_change 合计 | 对账对象 |
|---|---:|---|
| product_category | -266357.20000000 | 总体 GMV 净变化，精确一致 |
| customer_state | -266357.20000000 | 总体 GMV 净变化，精确一致 |
| seller | -266357.20000000 | 总体 GMV 净变化，精确一致 |
| SP category | -79511.75000000 | SP 净变化，精确一致 |
| SP seller | -79511.75000000 | SP 净变化，精确一致 |

SP 两种视角各自与父组对账，不要求局部下钻等于全体 GMV 变化。
