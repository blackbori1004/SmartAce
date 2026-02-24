# Aegis Ace Original Style Bible v1

## 0) 목적
Aegis Ace 에이전트 아이덴티티 이미지를 **저작권/상표/IP 침해 없이**, 일관된 화풍으로 대량 생성하기 위한 기준.

---

## 1) 스타일 정체성 (Style DNA)
- 키워드: `clean`, `playful`, `symbolic`, `futuristic`, `trustworthy`
- 표현 톤: 친근하지만 과장되지 않음
- 기본 룩: 반실사 금지, 완전 실사 금지, 카툰/일러스트 기반

### 금지 규칙
- 특정 실존 작가/스튜디오/브랜드 화풍을 직접 지칭하거나 모사 금지
- 특정 캐릭터 IP 연상 요소(로고, 시그니처 실루엣, 의상 디테일) 금지
- 유명인 얼굴/실존인 유사도 높은 생성 금지

---

## 2) 시각 규칙

### 2.1 라인/형태
- 외곽선 두께: 중간(2~4px 느낌)
- 모서리: 곡선 우선
- 형태: 원형/타원형 기반, 날카로운 실루엣 최소화

### 2.2 색상 팔레트 (고정)
- Primary: `#0B1020`, `#111827`, `#1F2937`
- Accent Green: `#84CC16`, `#65A30D`, `#A3E635`
- Accent Blue: `#38BDF8`, `#0EA5E9`
- Accent Gold: `#F59E0B`, `#FBBF24`
- Neutrals: `#F8FAFC`, `#E5E7EB`, `#94A3B8`

### 2.3 조명/배경
- 조명: 소프트 키라이트 1개 + 약한 림라이트
- 배경: 단색 그라데이션 또는 심플 패턴
- 과한 텍스처/노이즈 금지

---

## 3) 캐릭터 구조
- 비율: 헤드 55~65%, 바디 35~45%
- 눈: 큰 원형/타원형, 하이라이트 1~2개
- 코: 최소화
- 입: 단순 선형
- 손/소품: 지나친 디테일 금지

### 표정 세트
- Calm, Confident, Curious, Energetic, Focused

---

## 4) 에디션 시스템
- Core / Rare / Mythic 3티어
- Trait Category
  - Headgear
  - Eye style
  - Accessory
  - Symbol
  - Background pattern
- 생성 키: `edition_id`, `seed`, `traits[]`, `timestamp`

---

## 5) 출력 규격
- 기본: 1024x1024 PNG
- 썸네일: 512x512 JPG
- 파일명 규칙: `AACE_<edition_id>_<seed>.png`

---

## 6) 품질 게이트
- Similarity check: 기존 에디션과 구조 유사도 상한
- Safety check: NSFW/폭력/혐오/정치 선동 제거
- IP check: 상표/캐릭터 연상 요소 필터
- Reject rule: 기준 미달 시 재생성

---

## 7) 프롬프트 시스템 원칙
- 고정 prefix + 변수 슬롯 구조 유지
- 네거티브 프롬프트 상시 포함
- 모델/샘플링 파라미터 범위 제한으로 일관성 유지

---

## 8) 라이선스 정책 (초안)
- 생성물은 Aegis Ace 플랫폼 라이선스 규정 적용
- 사용자 상업적 사용 여부는 플랜별 차등
- 제3자 IP 침해 신고 절차 포함
