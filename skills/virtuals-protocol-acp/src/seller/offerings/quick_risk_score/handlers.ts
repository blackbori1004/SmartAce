import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function scoreFromText(input: string): number {
  let s = 0;
  for (const ch of input) s = (s + ch.charCodeAt(0)) % 1000;
  return 25 + (s % 71); // 25..95
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const base = `${request?.target_type ?? "wallet"}:${request?.target_id ?? "unknown"}:${request?.chain ?? "base"}:${request?.focus ?? "volatility"}`;
  const riskScore = scoreFromText(base);

  const focus = String(request?.focus ?? "volatility");
  const topRisks = [
    focus === "concentration" ? "High allocation concentration" : "Short-term volatility pressure",
    "Liquidity depth uncertainty",
    "News/sentiment regime shift risk"
  ];

  const actions = [
    "Reduce position concentration toward diversified allocation",
    "Set clear stop/hedge threshold before next volatility window",
    "Review exposure sizing against downside scenario"
  ];

  return {
    deliverable: {
      type: "application/json",
      value: {
        risk_score: riskScore,
        risk_level: riskScore >= 75 ? "high" : riskScore >= 55 ? "medium" : "low",
        top_risks: topRisks,
        actions,
        confidence: "medium"
      }
    }
  };
}

export function validateRequirements(request: any): ValidationResult {
  const targetType = String(request?.target_type ?? "").toLowerCase();
  const targetId = String(request?.target_id ?? "").trim();
  const chain = String(request?.chain ?? "").toLowerCase();
  const focus = String(request?.focus ?? "").toLowerCase();

  const allowedTargetTypes = new Set(["wallet", "token"]);
  const allowedChains = new Set(["base", "ethereum", "arbitrum", "optimism", "polygon", "solana"]);
  const allowedFocus = new Set(["liquidation", "concentration", "volatility", "sentiment"]);

  if (!allowedTargetTypes.has(targetType))
    return { valid: false, reason: "target_type must be wallet|token" };
  if (!targetId || targetId.length < 2)
    return { valid: false, reason: "target_id is required" };
  if (!allowedChains.has(chain))
    return { valid: false, reason: "chain must be one of: base, ethereum, arbitrum, optimism, polygon, solana" };
  if (!allowedFocus.has(focus))
    return { valid: false, reason: "focus must be liquidation|concentration|volatility|sentiment" };

  return { valid: true };
}

export function requestPayment(): string {
  return "Quick Risk Score accepted. Please proceed with payment to receive instant structured output.";
}
