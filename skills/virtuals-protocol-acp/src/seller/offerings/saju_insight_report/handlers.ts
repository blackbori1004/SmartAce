import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";

function biasFromDate(date: string): number {
  return [...date].reduce((a, c) => a + c.charCodeAt(0), 0) % 100;
}

export async function executeJob(request: any): Promise<ExecuteJobResult> {
  const birthDate = String(request?.birth_date ?? "");
  const question = String(request?.question ?? "");
  const lang = String(request?.language ?? "ko");
  const bias = biasFromDate(birthDate);

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
  if (!request?.birth_date || !request?.question) {
    return { valid: false, reason: "Missing required fields: birth_date, question" };
  }
  return { valid: true };
}

export function requestPayment(): string {
  return "Saju Insight report accepted. Please proceed with payment.";
}
