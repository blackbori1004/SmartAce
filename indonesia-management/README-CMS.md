# One Day Korea Page — Netlify CMS (Decap) Setup

이 프로젝트는 **기존 HTML 퀄리티 유지** + **문구/사진을 웹에서 편집**할 수 있게 구성되어 있습니다.

## 포함된 파일

- `one-day-korea-package-live.html` → 실제 랜딩 페이지
- `data/site.json` → 문구/패키지/사진/연락처 데이터
- `admin/index.html` → CMS 관리자 페이지
- `admin/config.yml` → CMS 필드 설정
- `assets/uploads/` → CMS 업로드 이미지 저장 폴더

## 동작 방식

- 랜딩 페이지는 `data/site.json`을 읽어 화면을 채웁니다.
- `/admin`에서 내용을 수정하면 Git 커밋으로 저장되고 배포에 반영됩니다.

---

## Netlify 배포 (B 방식)

1. 이 폴더가 들어있는 레포를 GitHub에 push
2. Netlify에서 **Import from Git**
3. Build settings
   - Build command: (비워도 됨)
   - Publish directory: `indonesia-management`
4. Site deploy 완료 후
   - Netlify > **Identity** > Enable Identity
   - Registration preferences: `Invite only` 추천
   - **Git Gateway**: Enable
5. Identity에서 관리자 이메일 초대
6. 배포 도메인 + `/admin` 접속해서 로그인

예: `https://your-site.netlify.app/admin`

---

## 수정 포인트 (관리자 화면에서)

- Hero 문구
- KPI 4개
- 패키지 카드/가격/불릿
- 갤러리 사진/캡션
- WhatsApp 번호(`ownerWa`)와 빠른문의 문구
- Footer

> WhatsApp 번호는 숫자만 입력: `6281234567890`

---

## 로컬에서 CMS 테스트

로컬 테스트 시(선택):

```bash
npx decap-server
```

그 뒤 정적 서버를 띄우고 `/admin` 접속하면 `local_backend: true` 설정으로 로컬 편집 테스트 가능.
