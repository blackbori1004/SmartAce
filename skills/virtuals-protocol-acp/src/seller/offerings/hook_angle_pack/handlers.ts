import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";
const req=(request:any)=>request?.requirement??request??{};

export async function executeJob(request:any): Promise<ExecuteJobResult>{
  const r=req(request);
  const offer=String(r.offer_name);
  const aud=String(r.target_audience);
  const goal=String(r.goal);
  const tone=String(r.tone??"trust");

  const hooks = [
    `Most ${aud} lose conversions before they even explain the offer — ${offer} fixes that fast.`,
    `Before you post again, run this ${goal}-first angle for ${offer}.`,
    `${offer}: the shortest path from interest to ${goal}.`,
    `Stop writing generic copy. ${offer} gives ${aud} a reason to act now.`,
    `If your funnel is quiet, this ${offer} hook is your reset button.`,
    `${aud} don’t need more noise — they need a clear reason to start.`,
    `One message, one CTA, one action: that’s how ${offer} converts.`,
    `You don't need more traffic. You need the right first sentence for ${offer}.`,
    `Try this ${tone} opener and watch response quality change immediately.`,
    `${offer} is built for action, not impressions.`
  ];

  return { deliverable: { type:"application/json", value:{ offer_name:offer, audience:aud, goal, tone, hooks } } };
}

export function validateRequirements(request:any): ValidationResult{
  const r=req(request);
  if(!r.offer_name) return {valid:false, reason:"offer_name is required"};
  if(!r.target_audience) return {valid:false, reason:"target_audience is required"};
  if(!["clicks","starts","replies"].includes(String(r.goal))) return {valid:false, reason:"goal must be clicks|starts|replies"};
  if(r.tone && !["bold","trust","educational"].includes(String(r.tone))) return {valid:false, reason:"tone must be bold|trust|educational"};
  return {valid:true};
}

export function requestPayment(){ return "Hook pack accepted. Generating 10 conversion-first hooks."; }
