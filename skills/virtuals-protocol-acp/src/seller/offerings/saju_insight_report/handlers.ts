import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function biasFromBirth(y: number, m: number, d: number, h: number, g: string): number {
  const seed = `${y}-${m}-${d}-${h}-${g}`;
  return [...seed].reduce((a, c) => a + c.charCodeAt(0), 0) % 100;
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const birthYear = Number(request?.birth_year ?? 0);
  const birthMonth = Number(request?.birth_month ?? 0);
  const birthDay = Number(request?.birth_day ?? 0);
  const birthHour = Number(request?.birth_hour ?? 0);
  const gender = String(request?.gender ?? "male");
  const question = String(request?.question ?? "");
  const lang = String(request?.language ?? "ko");
  const bias = biasFromBirth(birthYear, birthMonth, birthDay, birthHour, gender);

  const ko = {
    theme: bias > 50 ? "확장보다 정리와 내실이 유리한 흐름" : "새 시도와 학습 확장이 유리한 흐름",
    actions: [
      "핵심 우선순위 1개를 2주간 고정해 실행하세요.",
      "감정 기반 결정보다 체크리스트 기반 결정을 권장합니다.",
      "중요 대화/계약은 하루 숙성 후 확정하세요."
    ]
  };

  const en = {
    theme: bias > 50 ? "A consolidation-focused phase is favored over expansion." : "A learning-and-expansion phase is favored.",
    actions: [
      "Commit to one top priority for 14 days.",
      "Prefer checklist-based decisions over emotion-led decisions.",
      "Sleep on major commitments before finalizing."
    ]
  };

  const selected = lang.startsWith("ko") ? ko : en;

  return {
    deliverable: {
      type: "application/json",
      value: {
        question,
        theme_summary: selected.theme,
        personality_tendencies: ["analytical", "persistent", "sensitive to uncertainty"],
        action_suggestions: selected.actions,
        disclaimer: "For reflection/entertainment only. Not medical, legal, or investment advice."
      }
    }
  };
}

export function validateRequirements(request: any): ValidationResult {
  const y = Number(request?.birth_year ?? 0);
  const m = Number(request?.birth_month ?? 0);
  const d = Number(request?.birth_day ?? 0);
  const h = Number(request?.birth_hour ?? -1);
  const g = String(request?.gender ?? "");

  if (!Number.isInteger(y) || y < 1900 || y > 2100) {
    return { valid: false, reason: "birth_year must be a valid year (1900-2100)" };
  }
  if (!Number.isInteger(m) || m < 1 || m > 12) {
    return { valid: false, reason: "birth_month must be 1-12" };
  }
  if (!Number.isInteger(d) || d < 1 || d > 31) {
    return { valid: false, reason: "birth_day must be 1-31" };
  }
  if (!Number.isInteger(h) || h < 0 || h > 23) {
    return { valid: false, reason: "birth_hour must be 0-23" };
  }
  if (!["male", "female"].includes(g)) {
    return { valid: false, reason: "gender must be male or female" };
  }
  if (!request?.question) {
    return { valid: false, reason: "question is required" };
  }

  return { valid: true };
}

export function requestPayment(): string {
  return "Saju Insight report accepted. Please proceed with payment.";
}
