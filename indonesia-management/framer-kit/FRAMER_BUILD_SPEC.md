# Framer Build Spec — One Day Korea Trip (ID 20s Target)

## Goal
Build a **production-ready, always-on landing page** in Framer for Indonesian travelers in their 20s who are visiting Korea.

Primary conversion = **WhatsApp booking click**.

---

## 1) Site Structure (Single Landing Page)

### Section A — Hero
- Badge: `BOOKING OPEN · Jakarta/Surabaya/Medan Travelers Welcome`
- Headline:
  `One Day Korea Trip untuk Traveler Indonesia 20-an 🇮🇩✨🇰🇷`
- Subtext:
  `Rute anti-ribet, spot viral, café aesthetic, dan jadwal yang langsung bisa dipakai. Cocok buat first timer, bestie trip, atau solo trip.`
- CTA 1 (Primary): `Booking via WhatsApp`
- CTA 2 (Secondary): `Lihat Paket`
- KPI mini blocks:
  - `10–12 jam`
  - `2–6 pax`
  - `Mulai ₩129,000`
  - `Instant Booking`

### Section B — Paket Cards (CMS powered)
Card fields:
- Cover image
- Paket name
- Price
- Short description
- 4 highlights
- CTA button: `Pilih Paket Ini`

### Section C — Why Us
3~4 benefit blocks:
- `Route optimized (hemat waktu)`
- `Photo + trend spots curated`
- `Halal-friendly options`
- `Bahasa Indonesia support`

### Section D — Sample Timeline
Show 1 day schedule preview (hour blocks):
- 09:00 Meet point
- 10:00 Area 1
- 12:00 Lunch
- 14:00 Area 2
- 17:00 Sunset spot
- 19:00 Night spot

### Section E — Social Proof
- 3 testimonial cards
- Optional: IG/TikTok embed block

### Section F — FAQ
At least:
1. Included / not included?
2. Is halal food available?
3. Payment and confirmation process?
4. Reschedule / cancellation?
5. Private trip possible?

### Section G — Final CTA
- Headline: `Tanggalmu siap? Tinggal chat, kami bantu atur.`
- Button: `Chat WhatsApp Sekarang`

### Floating sticky button
- Bottom-right: `💬 Booking WhatsApp`

---

## 2) Framer CMS Collections

Create collections:

### Collection: `Packages`
Fields:
- `slug` (text)
- `name` (text)
- `price` (text)
- `short_desc` (text)
- `highlight_1` (text)
- `highlight_2` (text)
- `highlight_3` (text)
- `highlight_4` (text)
- `cover_image` (image)
- `wa_template` (long text)
- `is_active` (boolean)

### Collection: `Testimonials`
Fields:
- `name`
- `origin_city`
- `quote`
- `rating` (number)
- `avatar` (image)

### Collection: `FAQ`
Fields:
- `question`
- `answer`
- `order` (number)

---

## 3) WhatsApp Conversion Logic

Use format:
`https://wa.me/<YOUR_NUMBER>?text=<ENCODED_MESSAGE>`

Recommended default message:
`Halo! Saya tertarik One Day Korea Trip. Bisa cek slot tanggal dan paket yang cocok buat saya?`

For package-specific buttons, append package info:
`Halo! Saya mau booking paket: {{name}} ({{price}}).`

---

## 4) Copy Blocks (ready to paste)

## Hero Headline
`One Day Korea Trip untuk Traveler Indonesia 20-an`

## Hero Sub
`Nikmati Korea tanpa ribet: route efisien, spot hits, dan itinerary yang langsung bisa dijalankan dalam 1 hari.`

## Final CTA Headline
`Siap berangkat? Kami bantu dari pilih paket sampai hari-H.`

## Final CTA Sub
`Chat sekarang, dapat rekomendasi paket sesuai budget & style trip kamu.`

---

## 5) Design Direction (Framer)

- Theme: dark + purple/mint accent
- Corner radius: 14~20
- Card shadow: soft
- Font pairing:
  - Heading: Inter / Sora bold
  - Body: Inter regular
- Mobile-first spacing:
  - section top/bottom: 56~80
  - card gap: 12~16

---

## 6) SEO Basics (Framer Settings)

- Title: `One Day Korea Trip untuk Traveler Indonesia | Booking WhatsApp`
- Description: `Paket one day Korea untuk traveler Indonesia usia 20-an. Booking cepat via WhatsApp. Rute trend, kuliner, dan spot foto terbaik.`
- OG image: cover package image (1200x630)
- Keywords: `paket korea, one day korea, wisata korea, travel korea indonesia, seoul trip`

---

## 7) Launch Checklist

- [ ] Replace WhatsApp number
- [ ] Upload package images
- [ ] Add 3+ real testimonials
- [ ] Check mobile layout on 390px width
- [ ] Test all CTA links
- [ ] Connect custom domain
- [ ] Publish

---

## 8) Recommended Weekly Optimization

Week 1:
- A/B Hero headline (emotional vs practical)
- Track button CTR (top CTA vs sticky CTA)

Week 2:
- Test price framing (`mulai` vs `best value` label)
- Add urgency line (`Slot weekend cepat penuh`)

Week 3:
- Add language toggle (ID / EN)
- Add “Top 3 most booked routes” block
