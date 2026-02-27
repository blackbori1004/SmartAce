import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function getReq(request: any): Record<string, any> {
  return request?.requirement ?? request ?? {};
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const r = getReq(request);
  const strategyName = String(r.strategy_name ?? "unnamed_strategy");
  const markets = Array.isArray(r.markets) ? r.markets.map(String) : [];
  const timeframe = String(r.timeframe ?? "intraday");
  const targetReturn = Number(r.target_return_pct ?? 10);
  const maxDd = Number(r.max_drawdown_pct ?? 5);
  const capital = Number(r.capital_usd ?? 1000);

  const perTradeRiskPct = Math.max(0.25, Math.min(1.5, maxDd / 5));
  const maxConcurrent = Math.max(1, Math.min(5, Math.floor(markets.length / 2) || 2));
  const maxSingleExposurePct = Math.max(15, Math.min(35, 100 / Math.max(2, markets.length)));

  const plan = {
    strategy: {
      name: strategyName,
      timeframe,
      targetReturnPct: targetReturn,
      maxDrawdownPct: maxDd,
      tradableMarkets: markets
    },
    capitalModel: {
      totalCapitalUsd: capital,
      perTradeRiskPct,
      riskPerTradeUsd: Number(((capital * perTradeRiskPct) / 100).toFixed(2)),
      maxConcurrentPositions: maxConcurrent,
      maxSingleAssetExposurePct: maxSingleExposurePct
    },
    guardrails: {
      hardStop: `Pause new entries when daily drawdown >= ${Math.max(2, maxDd / 2).toFixed(1)}%`,
      softStop: "Reduce new position sizing by 50% after 2 consecutive losses",
      leverageCap: "Cap leverage at 5x for majors, 3x for high-volatility assets",
      executionRules: [
        "Use limit or protected market entries with slippage bounds",
        "Set SL immediately after fill",
        "Never average down after stop-out"
      ]
    },
    monitoring: {
      checkIntervalMinutes: 15,
      requiredMetrics: ["winRate", "profitFactor", "maxDrawdown", "exposureByAsset"],
      weeklyReview: "Rebalance risk limits based on realized volatility"
    }
  };

  return { deliverable: JSON.stringify(plan) };
}

export function validateRequirements(request: any): ValidationResult {
  const r = getReq(request);

  if (!r.strategy_name || String(r.strategy_name).trim().length < 3)
    return { valid: false, reason: "strategy_name is required (min 3 chars)" };

  if (!Array.isArray(r.markets) || r.markets.length === 0)
    return { valid: false, reason: "markets must be a non-empty array" };

  const invalidMarket = r.markets.some((m: any) => !m || String(m).trim().length < 3);
  if (invalidMarket)
    return { valid: false, reason: "each market must be a valid symbol/pair string" };

  const maxDd = Number(r.max_drawdown_pct);
  const capital = Number(r.capital_usd);

  if (!Number.isFinite(maxDd) || maxDd <= 0 || maxDd > 50)
    return { valid: false, reason: "max_drawdown_pct must be > 0 and <= 50" };

  if (!Number.isFinite(capital) || capital < 100)
    return { valid: false, reason: "capital_usd must be >= 100" };

  if (r.target_return_pct != null) {
    const target = Number(r.target_return_pct);
    if (!Number.isFinite(target) || target <= 0 || target > 500)
      return { valid: false, reason: "target_return_pct must be > 0 and <= 500" };
  }

  return { valid: true };
}

export function requestPayment(): string {
  return "Premium strategy risk blueprint request accepted. Processing after payment.";
}
