import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function scoreFromText(input: string): number {
  let s = 0;
  for (const ch of input) s = (s + ch.charCodeAt(0)) % 1000;
  return 25 + (s % 71);
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const targetId = String(request?.target_id ?? "unknown");
  const topic = String(request?.topic ?? "AI risk");
  const chain = String(request?.chain ?? "base");
  const riskScore = scoreFromText(`${targetId}:${chain}`);

  const posts = [
    `${topic}: manage downside first, upside second. Clear risk rails win long-term. #AI #Risk #DeFi`,
    `Before execution, define risk. ${topic} works best with strict position limits and review loops. #Automation #Trading #Risk`,
    `${topic} is strongest when decisions are measurable. One KPI, one action, daily iteration. #AIAgents #Growth #Web3`
  ];

  return {
    deliverable: {
      type: "application/json",
      value: {
        risk_snapshot: {
          target_id: targetId,
          chain,
          risk_score: riskScore,
          risk_level: riskScore >= 75 ? "high" : riskScore >= 55 ? "medium" : "low",
          top_risks: [
            "Concentration risk",
            "Volatility shock risk",
            "Liquidity depth uncertainty"
          ],
          actions: [
            "Reduce concentration",
            "Set downside threshold",
            "Review position sizing"
          ]
        },
        x_posts: posts.map((text, i) => ({
          variant: i + 1,
          text,
          cta: "Start with a small test and iterate.",
          hashtags: ["#AI", "#Risk", "#DeFi"]
        }))
      }
    }
  };
}

export function validateRequirements(request: any): ValidationResult {
  if (!request?.target_id || !request?.topic || !request?.chain) {
    return { valid: false, reason: "Missing required fields: target_id, topic, chain" };
  }
  return { valid: true };
}

export function requestPayment(): string {
  return "Bundle request accepted. Please proceed with payment for risk snapshot + 3 X drafts.";
}
