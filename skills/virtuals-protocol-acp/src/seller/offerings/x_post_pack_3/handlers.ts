import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function clip(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(0, maxChars - 1))}…`;
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const topic = String(request?.topic ?? "AI automation");
  const audience = String(request?.audience ?? "general");
  const tone = String(request?.tone ?? "trust");
  const maxChars = Number(request?.max_chars ?? 240);

  const posts = [
    `${topic} is easier when your ${audience} workflow has clear signals. Start simple, ship daily, improve weekly.`,
    `Most teams overcomplicate ${topic}. The edge is consistent execution + clear feedback loops. Build, measure, refine.`,
    `If ${topic} feels noisy, use one KPI and one action at a time. Momentum beats perfection.`
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
          cta: tone === "bold" ? "Try it today." : "Test this approach this week.",
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
  return "X Post Pack accepted. Please proceed with payment to receive 3 post variants.";
}
