import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";
const req=(request:any)=>request?.requirement??request??{};

export async function executeJob(request:any): Promise<ExecuteJobResult>{
  const r=req(request);
  const offer=String(r.offer_name);
  const obj=String(r.objection);
  const target=String(r.target);
  const tone=String(r.tone??"direct");

  const replies = Array.from({length:10}).map((_,i)=>({
    id:i+1,
    text:`(${tone}) Totally fair point about "${obj}". For ${target}, ${offer} is designed to reduce decision time and give ready-to-use output immediately. If useful, I can share a quick sample before you commit.`
  }));

  return { deliverable:{ type:"application/json", value:{ offer_name:offer, objection:obj, target, tone, replies } } };
}

export function validateRequirements(request:any): ValidationResult{
  const r=req(request);
  if(!r.offer_name) return {valid:false, reason:"offer_name is required"};
  if(!r.objection || String(r.objection).trim().length<3) return {valid:false, reason:"objection is required"};
  if(!r.target) return {valid:false, reason:"target is required"};
  if(r.tone && !["friendly","direct","formal"].includes(String(r.tone))) return {valid:false, reason:"tone must be friendly|direct|formal"};
  return {valid:true};
}

export function requestPayment(){ return "DM reply pack accepted. Creating 10 conversion replies now."; }
