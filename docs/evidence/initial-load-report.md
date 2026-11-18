# Initial load report (T15)

Date: 2026-11-18  
Operational detail: [`docs/reports/phase6-run6_4.md`](../reports/phase6-run6_4.md)

## Summary

Initial Locust run against local prod-like StockPilot (`stockpilot-prodlike` + observability). Session/OIDC auth through Caddy (`https://stockpilot.local`). Documented **down-scale** of AGENTS §27.4 reference dataset/hardware; **design-goal targets unchanged**.

## Recorded numbers

| Item | Value |
|---|---|
| Image | `stockpilot-backend:localprod` `sha256:f7b2c37879b8…`; `stockpilot-edge:localprod` `sha256:d53a72a8bda4…` |
| Hardware | Windows Docker Desktop; i5-12400F 12 logical CPUs; 15.8 GiB RAM; Locust on same compose network |
| Data volume | 10 load tenants; 1 000 products; 2 000 seed drafts + live Locust orders |
| Scenario | 20 min shape: warm-up → 15 VU steady → 30 VU spike; ~70/30 read/command |
| Steady read p95 | ~39 ms (Locust); ~36 ms (Prometheus HTTP histogram) |
| Steady command p95 | ~54 ms |
| Steady errors | 0% |
| Stock | `balance-check` mismatches = 0 |

Artifacts (gitignored): `tests/load/results/locust.html`, `locust_stats*.csv`, `phase_summary.json`.
