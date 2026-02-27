import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function getReq(request: any): Record<string, any> {
  return request?.requirement ?? request ?? {};
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const r = getReq(request);
  const market = String(r.market ?? "UNKNOWN");
  const entry = Number(r.entry ?? 0);
  const leverage = Number(r.leverage ?? 1);
  const maxLossPct = Number(r.max_loss_pct ?? 2);

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
  const r = getReq(request);
  if (!r.market || String(r.market).trim().length < 3)
    return { valid: false, reason: "market is required (e.g. ETH/USDC)" };

  const entry = Number(r.entry);
  const leverage = Number(r.leverage);
  const maxLossPct = Number(r.max_loss_pct);

  if (!Number.isFinite(entry) || entry <= 0)
    return { valid: false, reason: "entry must be a positive number" };
  if (!Number.isFinite(leverage) || leverage < 1 || leverage > 50)
    return { valid: false, reason: "leverage must be between 1 and 50" };
  if (!Number.isFinite(maxLossPct) || maxLossPct <= 0 || maxLossPct > 20)
    return { valid: false, reason: "max_loss_pct must be > 0 and <= 20" };

  return { valid: true };
}

export function requestPayment(): string {
  return "Risk guard analysis prepared. Requesting payment to deliver guardrails.";
}
