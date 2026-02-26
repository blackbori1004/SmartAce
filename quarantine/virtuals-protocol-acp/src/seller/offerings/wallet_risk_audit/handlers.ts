import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const wallet = String(request?.requirement?.wallet ?? "");
  const chain = String(request?.requirement?.chain ?? "base");
  const mode = String(request?.requirement?.risk_mode ?? "balanced");

  const suggestions = {
    conservative: {
      maxSingleAssetPct: 25,
      minStablePct: 40,
      rebalance: "weekly",
    },
    balanced: {
      maxSingleAssetPct: 35,
      minStablePct: 25,
      rebalance: "weekly",
    },
    aggressive: {
      maxSingleAssetPct: 50,
      minStablePct: 10,
      rebalance: "daily",
    },
  } as const;

  const picked = (suggestions as any)[mode] ?? suggestions.balanced;

  const report = {
    wallet,
    chain,
    riskMode: mode,
    checks: [
      "Concentration risk review",
      "Stablecoin buffer check",
      "Volatility exposure check"
    ],
    guardrails: {
      maxSingleAssetPct: picked.maxSingleAssetPct,
      minStablePct: picked.minStablePct,
      rebalanceFrequency: picked.rebalance,
      killSwitchRule: "Pause new risk if portfolio drawdown exceeds 7% in 24h"
    },
    note: "Template audit. Connect on-chain indexer for full holdings decomposition."
  };

  return { deliverable: JSON.stringify(report) };
}

export function validateRequirements(request: any): ValidationResult {
  const r = request?.requirement ?? {};
  if (!r.wallet) return { valid: false, reason: "wallet is required" };
  if (!r.chain) return { valid: false, reason: "chain is required" };
  return { valid: true };
}

export function requestPayment(): string {
  return "Wallet risk audit request accepted. Processing after payment.";
}
