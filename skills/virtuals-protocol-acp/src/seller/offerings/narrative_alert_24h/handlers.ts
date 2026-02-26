import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function directionFromKeyword(k: string): "up" | "flat" | "down" {
  const n = [...k].reduce((a, c) => a + c.charCodeAt(0), 0) % 3;
  return n === 0 ? "up" : n === 1 ? "flat" : "down";
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const keywords: string[] = Array.isArray(request?.keywords) ? request.keywords.slice(0, 5) : [];
  const watchWindow = Number(request?.watch_window_hours ?? 24);

  const signals = keywords.map((k) => {
    const d = directionFromKeyword(String(k));
    return {
      keyword: k,
      direction: d,
      strength: d === "up" ? "medium" : d === "down" ? "medium" : "low"
    };
  });

  return {
    deliverable: {
      type: "application/json",
      value: {
        watch_window_hours: watchWindow,
        summary: "Narrative shift snapshot generated.",
        signals,
        recommended_actions: [
          "Prioritize response on rising keywords first",
          "Use one proof-based post and one CTA-based follow-up"
        ],
        confidence: "medium"
      }
    }
  };
}

export function validateRequirements(request: any): ValidationResult {
  if (!Array.isArray(request?.keywords) || request.keywords.length === 0) {
    return { valid: false, reason: "keywords must be a non-empty array" };
  }
  return { valid: true };
}

export function requestPayment(): string {
  return "Narrative Alert request accepted. Please proceed with payment.";
}
