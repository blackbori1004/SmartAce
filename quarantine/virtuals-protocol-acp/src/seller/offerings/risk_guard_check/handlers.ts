import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const market = String(request?.requirement?.market ?? "UNKNOWN");
  const entry = Number(request?.requirement?.entry ?? 0);
  const leverage = Number(request?.requirement?.leverage ?? 1);
  const maxLossPct = Number(request?.requirement?.max_loss_pct ?? 2);

  const riskTier = leverage >= 10 ? "HIGH" : leverage >= 5 ? "MEDIUM" : "LOW";
  const recommendedPositionUsd = Math.max(20, Math.round(1000 / Math.max(1, leverage)));
  const stopLossPct = Math.max(0.8, Math.min(maxLossPct, 3.0));
  const takeProfitPct = Number((stopLossPct * 2.5).toFixed(2));
  const killSwitch = `Pause trading if ${market} daily drawdown exceeds ${maxLossPct}%`;

  const deliverable = {
    market,
    riskTier,
    entry,
    leverage,
    recommendations: {
      maxPositionUsd: recommendedPositionUsd,
      stopLossPct,
      takeProfitPct,
      killSwitch,
      checklist: [
        "Use post-only or tight slippage limits",
        "Avoid adding size after 2 consecutive losses",
        "Re-evaluate position every 15 minutes"
      ]
    }
  };

  return { deliverable: JSON.stringify(deliverable) };
}

export function validateRequirements(request: any): ValidationResult {
  const r = request?.requirement ?? {};
  if (!r.market) return { valid: false, reason: "market is required" };
  if (Number(r.entry) <= 0) return { valid: false, reason: "entry must be > 0" };
  if (Number(r.leverage) <= 0) return { valid: false, reason: "leverage must be > 0" };
  if (Number(r.max_loss_pct) <= 0) return { valid: false, reason: "max_loss_pct must be > 0" };
  return { valid: true };
}

export function requestPayment(): string {
  return "Risk guard analysis prepared. Requesting payment to deliver guardrails.";
}
