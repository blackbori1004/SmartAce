import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";
const req=(request:any)=>request?.requirement??request??{};

export async function executeJob(request:any): Promise<ExecuteJobResult>{
  const r=req(request);
  const agent=String(r.agent_name);
  const focus=String(r.offer_focus);
  const aud=String(r.audience);
  const goal=String(r.goal);

  const days = Array.from({length:7}).map((_,i)=>(
    {
      day:i+1,
      topic:`${focus} angle #${i+1}`,
      post:`${agent}: ${focus} for ${aud}. Outcome this post targets: ${goal}.`,
      cta:`If this fits your use-case, start with the entry offer today.`,
      follow_up:`Send 1 direct follow-up to a warm lead within 24h.`
    }
  ));

  return { deliverable:{ type:"application/json", value:{ agent_name:agent, offer_focus:focus, audience:aud, goal, calendar:days } } };
}

export function validateRequirements(request:any): ValidationResult{
  const r=req(request);
  for (const k of ["agent_name","offer_focus","audience","goal"]) {
    if (!r[k] || String(r[k]).trim().length<2) return {valid:false, reason:`${k} is required`};
  }
  if (!["starts","leads","completed"].includes(String(r.goal))) return {valid:false, reason:"goal must be starts|leads|completed"};
  return {valid:true};
}

export function requestPayment(){ return "7-day calendar request accepted. Preparing daily plan."; }
