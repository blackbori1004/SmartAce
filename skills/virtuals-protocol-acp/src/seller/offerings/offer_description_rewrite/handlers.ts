import type { ExecuteJobResult, ValidationResult } from "../../runtime/offeringTypes.js";
const req=(request:any)=>request?.requirement??request??{};

export async function executeJob(request:any): Promise<ExecuteJobResult>{
  const r=req(request);
  const offer=String(r.offer_name);
  const desc=String(r.current_description);
  const aud=String(r.target_audience);
  const price=Number(r.price);

  const rewritten = `${offer} for ${aud}: clear, fast, and deployable output.\n\nWhat you get:\n- specific deliverable in one response\n- actionable format you can use immediately\n- one focused CTA to increase starts\n\nPrice: $${price.toFixed(2)}\nBest next step: pair this with a follow-up message pack for higher conversion.`;

  return { deliverable: { type:"application/json", value:{ offer_name:offer, original_length:desc.length, rewritten_description:rewritten, cta:"Start now and deploy in minutes." } } };
}

export function validateRequirements(request:any): ValidationResult{
  const r=req(request);
  if(!r.offer_name) return {valid:false, reason:"offer_name is required"};
  if(!r.current_description || String(r.current_description).length < 20) return {valid:false, reason:"current_description too short"};
  if(!r.target_audience) return {valid:false, reason:"target_audience is required"};
  if(!Number.isFinite(Number(r.price)) || Number(r.price) < 0) return {valid:false, reason:"price must be non-negative number"};
  return {valid:true};
}

export function requestPayment(){ return "Description rewrite accepted. Generating conversion-first copy."; }
