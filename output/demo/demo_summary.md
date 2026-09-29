# BusinessInsight Demo

Mode: offline

Question: Why did Product GMV decline, and what were the main drivers?

Status: completed_replay

Fallback: False

Business Question → Data Inspection → Metric Analysis → Anomaly Detection → Root Cause Analysis → Evidence Validation → Business Report → Tableau Dashboard

Offline/fallback is saved deterministic evidence replay, not live LLM reasoning. Tableau was built and verified by the user.

```text
Selected Period: 2017-11 → 2017-12
Product GMV: 1,010,271.37 → 743,914.17
MoM: -26.36%
Primary Metric Driver: Order Volume
Contribution: 91.87%
Largest Category Contributor: cama_mesa_banho
Contribution: 14.61%
Largest State Contributor: SP
Contribution: 29.85%
Largest Seller Contributor: 7e93a43ef30c4f03f38b393420bc753a
Contribution: 7.28%
```

Report: output/reports/agent_business_report.md

Dashboard: output/tableau/BusinessInsight_Dashboard.twb
