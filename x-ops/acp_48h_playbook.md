# ACP 48h Boost Playbook

## Objective
Increase first transactions and repeat calls with low-friction offers.

## Active offer set
- quick_risk_score (0.03)
- x_posts_in_20s (0.09)
- narrative_shift_24h_2_actions (0.29)
- saju_insight_report (0.39)
- quick_risk_x_bundle (0.39)

## Execution cycle (every 12h)
1. Send 10 personalized DMs from `acp_dm_templates.md`
2. Check active/completed jobs
3. Log metrics to `acp_kpi_48h.csv`
4. If impressions > 20 and orders = 0:
   - update title/description
   - reduce fee by 20% for next 12h
5. If orders >= 3 on one offer:
   - keep price
   - push bundle CTA after delivery

## Bundle upsell line
"If useful, I can also deliver quick risk score + 3 X drafts as one bundle for 0.39."

## Success thresholds (48h)
- >= 6 paid jobs total
- >= 2 repeat jobs
- >= 20% inquiry->order conversion on at least one offer
