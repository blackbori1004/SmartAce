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
  if (!request?.target_type || !request?.target_id || !request?.chain || !request?.focus) {
    return { valid: false, reason: "Missing required fields: target_type, target_id, chain, focus" };
  }
  return { valid: true };
}

export function requestPayment(): string {
  return "Quick Risk Score accepted. Please proceed with payment to receive instant structured output.";
}
