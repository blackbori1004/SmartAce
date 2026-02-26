import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function clip(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(0, maxChars - 1))}…`;
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const topic = String(request?.topic ?? "AI automation");
  const audience = String(request?.audience ?? "general");
  const tone = String(request?.tone ?? "trust");
  const maxChars = 240;

  const posts = [
    `${topic}: ship fast for ${audience} users, then optimize by feedback loops.`,
    `Most teams overcomplicate ${topic}. Clear promise + clear CTA wins faster.`,
    `${topic} in one line: measurable value, repeatable workflow, rapid iteration.`
  ].map((p) => clip(`${p} #AI #Automation #Growth`, maxChars));

  return {
    deliverable: {
      type: "application/json",
      value: {
        topic,
        tone,
        posts: posts.map((text, i) => ({
          variant: i + 1,
          text,
          cta: "Run a small test today.",
          hashtags: ["#AI", "#Automation", "#Growth"]
        }))
      }
    }
  };
}

export function validateRequirements(request: any): ValidationResult {
  if (!request?.topic || !request?.audience || !request?.tone) {
    return { valid: false, reason: "Missing required fields: topic, audience, tone" };
  }
  return { valid: true };
}

export function requestPayment(): string {
  return "3 X Posts in 20s request accepted. Please proceed with payment.";
}
