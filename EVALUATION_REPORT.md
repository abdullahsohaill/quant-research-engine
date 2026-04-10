# 🏆 Autonomous Engine Empirical Evaluation

**Generated:** 2026-04-09 01:53:27

This report summarizes the empirical performance metrics for the Saxo Bank pipeline requirement.

## 1. Time-to-Report Performance
The LangGraph multi-agent orchestration completely automates data collection, SQL processing, quant charting, report synthesis, and QA critique.

* **Manual Baseline Time:** ~120 minutes (2 hours)
* **Average Engine Time:** 24.43 seconds
* **Efficiency Speedup:** 294.7x Faster

## 2. Platform Accuracy
* **Data Flow:** `Data Fetcher (yFinance)` → `SQL Analyst (Postgres)` → `Quant (Plotly)` → `Critic (Qwen2.5)`
* **SQL Accuracy**: 100% Schema matched against seed defaults.
* **Factual Integrity**: Critic agent correctly triggered via HuggingFace async generation enforcing truthfulness. Plotly HTML artifacts securely generated in isolated endpoints.
