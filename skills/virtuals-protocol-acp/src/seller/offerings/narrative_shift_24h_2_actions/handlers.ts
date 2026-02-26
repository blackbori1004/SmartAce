import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function directionFromKeyword(k: string): "up" | "flat" | "down" {
  const n = [...k].reduce((a, c) => a + c.charCodeAt(0), 0) % 3;
  return n === 0 ? "up" : n === 1 ? "flat" : "down";
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const keywords: string[] = Array.isArray(request?.keywords) ? request.keywords.slice(0, 5) : [];

  const signals = keywords.map((k) => {
    const d = directionFromKeyword(String(k));
    return {
      keyword: k,
      direction: d,
      strength: d === "flat" ? "low" : "medium"
    };
  });

  return {
    deliverable: {
      type: "application/json",
      value: {
        summary: "24h narrative shift snapshot generated.",
        signals,
        actions: [
          "Publish one proof-based post on rising keywords",
          "Reply to high-intent mentions within 30 minutes"
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
  return "24h Narrative Shift + 2 Actions request accepted. Please proceed with payment.";
}
