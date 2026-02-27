import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function getReq(request: any): Record<string, any> {
  return request?.requirement ?? request ?? {};
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const r = getReq(request);
  const wallet = String(r.wallet ?? "");
  const chain = String(r.chain ?? "base");
  const mode = String(r.risk_mode ?? "balanced");

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
  const r = getReq(request);
  const wallet = String(r.wallet ?? "").trim();
  const chain = String(r.chain ?? "").trim().toLowerCase();
  const mode = String(r.risk_mode ?? "balanced").trim().toLowerCase();

  const evmAddressRegex = /^0x[a-fA-F0-9]{40}$/;
  const allowedChains = new Set(["base", "ethereum", "arbitrum", "optimism", "polygon", "solana"]);
  const allowedModes = new Set(["conservative", "balanced", "aggressive"]);

  if (!evmAddressRegex.test(wallet))
    return { valid: false, reason: "wallet must be a valid EVM address (0x...)" };
  if (!allowedChains.has(chain))
    return { valid: false, reason: "chain must be one of: base, ethereum, arbitrum, optimism, polygon, solana" };
  if (r.risk_mode && !allowedModes.has(mode))
    return { valid: false, reason: "risk_mode must be conservative|balanced|aggressive" };

  return { valid: true };
}

export function requestPayment(): string {
  return "Wallet risk audit request accepted. Processing after payment.";
}
