# Aegis Ace Prompt Templates v1

## Global System Prefix (고정)
"Original mascot-style agent portrait, clean vector-like illustration, rounded forms, medium outline, soft lighting, high clarity, consistent Aegis Ace palette, no real person likeness, no existing IP resemblance, no logos, no text watermark"

## Negative Prompt (고정)
"photorealistic, celebrity likeness, copyrighted character, anime franchise style, brand logo, text watermark, low quality, blurry, distorted hands, extra limbs, gore, nsfw"

---

## Template Slots
- `{agent_role}`
- `{core_trait}`
- `{secondary_trait}`
- `{mood}`
- `{symbol}`
- `{headgear}`
- `{bg_theme}`

---

## 20 Prompt Variants
1. "{agent_role} avatar, {core_trait} + {secondary_trait}, {mood}, holding {symbol}, {headgear}, {bg_theme}"  
2. "Mascot portrait of {agent_role}, expressive eyes, {mood}, emblem: {symbol}, minimalist {bg_theme}"  
3. "Chibi-style agent, role={agent_role}, trait={core_trait}, accessory={symbol}, soft rim light"  
4. "Aegis-style guardian agent, {secondary_trait}, {headgear}, gradient background {bg_theme}"  
5. "Playful cyber helper, {agent_role}, calm smile, icon {symbol}, clean composition"  
6. "Professional AI agent portrait, {core_trait}, no realism, simple shading, {bg_theme}"  
7. "Friendly task agent, {mood}, symbolic prop {symbol}, rounded silhouette"  
8. "Focused decision agent, {core_trait}, elegant line work, subtle glow, {bg_theme}"  
9. "Analyst-type agent mascot, {agent_role}, {secondary_trait}, badge {symbol}"  
10. "Risk-control themed avatar, {agent_role}, confident stance, accessory {symbol}"  
11. "Explorer-type agent, {mood}, compact body ratio, {headgear}, clean backdrop"  
12. "Builder agent icon portrait, {core_trait}, minimal details, balanced palette"  
13. "Negotiator agent mascot, {secondary_trait}, hand prop {symbol}, soft shadows"  
14. "Strategist agent portrait, {mood}, elegant vector style, geometric {bg_theme}"  
15. "Guardian helper avatar, {core_trait}, minimal background, collectible look"  
16. "Community agent mascot, {agent_role}, warm expression, emblem {symbol}"  
17. "Automation assistant avatar, {secondary_trait}, icon prop {symbol}, high contrast"  
18. "Execution agent portrait, focused eyes, {headgear}, subtle gradient {bg_theme}"  
19. "Audit agent mascot, {core_trait}, tool-like symbol {symbol}, polished finish"  
20. "Premium edition avatar, role={agent_role}, {mood}, rare accessory {symbol}, collectible card framing"

---

## Recommended Params (예시)
- Steps: 28~40
- CFG: 5.5~7.0
- Sampler: DPM++ 2M Karras (or equivalent)
- Seed: 고정/랜덤 병행
- Size: 1024x1024
