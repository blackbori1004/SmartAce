import { validateRequirements as vQuick } from "../src/seller/offerings/quick_risk_score/handlers.ts";
import { validateRequirements as vGuard } from "../src/seller/offerings/risk_guard_check/handlers.ts";
import { validateRequirements as vWallet } from "../src/seller/offerings/wallet_risk_audit/handlers.ts";
import { validateRequirements as vStrategy } from "../src/seller/offerings/strategy_risk_plan/handlers.ts";

type Case = {
  name: string;
  fn: (r: any) => any;
  request: any;
  expectValid: boolean;
};

const cases: Case[] = [
  {
    name: "quick_risk_score valid",
    fn: vQuick,
    request: { target_type: "wallet", target_id: "0x1234", chain: "base", focus: "volatility" },
    expectValid: true,
  },
  {
    name: "quick_risk_score invalid chain",
    fn: vQuick,
    request: { target_type: "wallet", target_id: "0x1234", chain: "bitcoin", focus: "volatility" },
    expectValid: false,
  },
  {
    name: "risk_guard_check valid",
    fn: vGuard,
    request: { market: "ETH/USDC", entry: 2500, leverage: 5, max_loss_pct: 3 },
    expectValid: true,
  },
  {
    name: "risk_guard_check invalid leverage",
    fn: vGuard,
    request: { market: "ETH/USDC", entry: 2500, leverage: 80, max_loss_pct: 3 },
    expectValid: false,
  },
  {
    name: "wallet_risk_audit valid",
    fn: vWallet,
    request: { wallet: "0x1111111111111111111111111111111111111111", chain: "base", risk_mode: "balanced" },
    expectValid: true,
  },
  {
    name: "wallet_risk_audit invalid wallet",
    fn: vWallet,
    request: { wallet: "abc", chain: "base", risk_mode: "balanced" },
    expectValid: false,
  },
  {
    name: "strategy_risk_plan valid",
    fn: vStrategy,
    request: {
      strategy_name: "swing_alpha",
      markets: ["ETH/USDC", "BTC/USDC"],
      max_drawdown_pct: 12,
      capital_usd: 10000,
      target_return_pct: 30,
    },
    expectValid: true,
  },
  {
    name: "strategy_risk_plan invalid capital",
    fn: vStrategy,
    request: {
      strategy_name: "swing_alpha",
      markets: ["ETH/USDC"],
      max_drawdown_pct: 12,
      capital_usd: 50,
    },
    expectValid: false,
  },
  {
    name: "nested requirement compatibility (risk_guard_check)",
    fn: vGuard,
    request: { requirement: { market: "ETH/USDC", entry: 2500, leverage: 3, max_loss_pct: 2 } },
    expectValid: true,
  },
];

let pass = 0;
for (const tc of cases) {
  const out = tc.fn(tc.request);
  const valid = typeof out === "boolean" ? out : !!out?.valid;
  const ok = valid === tc.expectValid;
  if (ok) pass++;
  console.log(JSON.stringify({
    case: tc.name,
    expected: tc.expectValid,
    got: valid,
    result: ok ? "PASS" : "FAIL",
    reason: typeof out === "object" ? out?.reason ?? null : null,
  }));
}

console.log(`SUMMARY ${pass}/${cases.length} passed`);
if (pass !== cases.length) process.exit(1);
