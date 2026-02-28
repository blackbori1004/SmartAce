import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";
const req=(request:any)=>request?.requirement??request??{};

export async function executeJob(request:any): Promise<ExecuteJobResult>{
  const r=req(request);
  const offer=String(r.offer_name);
  const aud=String(r.target_audience);
  const goal=String(r.launch_goal);
  const cta=String(r.core_cta);

  return { deliverable:{ type:"application/json", value:{
    offer_name:offer,
    launch_goal:goal,
    assets:{
      hooks:[
        `${offer} for ${aud}: built to drive ${goal}`,
        `If ${goal} matters this week, start with ${offer}`,
        `Less noise, more starts: ${offer}`
      ],
      description:`${offer} helps ${aud} achieve ${goal} with structured, deploy-ready output. CTA: ${cta}`,
      outreach:[
        `Hey — we built ${offer} for ${aud}. If you're optimizing for ${goal}, this should fit your flow.`,
        `Quick idea: run ${offer} once, then decide if we scale together.`
      ]
    }
  } } };
}

export function validateRequirements(request:any): ValidationResult{
  const r=req(request);
  for (const k of ["offer_name","target_audience","launch_goal","core_cta"]) {
    if (!r[k] || String(r[k]).trim().length<3) return {valid:false, reason:`${k} is required`};
  }
  return {valid:true};
}

export function requestPayment(){ return "Launch content bundle accepted. Building all assets now."; }
