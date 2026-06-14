# 📱 StockAI PWA — iOS/Android 앱 배포 가이드

## 🚀 GitHub Pages 배포 순서 (10분 소요)

### 1단계 — GitHub 계정 만들기
1. https://github.com 접속 → Sign Up
2. 무료 계정으로 충분합니다

### 2단계 — 새 저장소(Repository) 만들기
1. GitHub 로그인 후 우상단 **+** → **New repository**
2. Repository name: `stockai` (영문 소문자)
3. **Public** 선택 (GitHub Pages 무료 사용 조건)
4. **Create repository** 클릭

### 3단계 — 파일 업로드
1. 방금 만든 저장소 페이지에서 **uploading an existing file** 클릭
2. 아래 파일들을 모두 드래그하여 업로드:
   ```
   index.html
   manifest.json
   sw.js
   icons/
     icon-192x192.png
     icon-512x512.png
   .github/
     workflows/
       deploy.yml
   ```
3. **Commit changes** 클릭

### 4단계 — GitHub Pages 활성화
1. 저장소 → **Settings** 탭
2. 왼쪽 메뉴 → **Pages**
3. Source: **GitHub Actions** 선택
4. 1~2분 기다리면 배포 완료

### 5단계 — 앱 주소 확인
- 배포 완료 후 주소: `https://[내GitHub아이디].github.io/stockai`
- 이 주소를 iOS/Android에서 열면 됩니다

---

## 📱 iPhone에 앱으로 설치

1. **Safari**로 위 주소 접속 (크롬은 안됨!)
2. 하단 공유 버튼 (□↑) 탭
3. **"홈 화면에 추가"** 탭
4. 이름 확인 후 **추가**
5. 홈 화면에 StockAI 아이콘 생성 완료 🎉

---

## 📱 Android에 앱으로 설치

1. **Chrome**으로 위 주소 접속
2. 주소창 우측 또는 메뉴(⋮) → **"앱 설치"** 또는 **"홈 화면에 추가"**
3. 또는 앱 내 **"📲 앱으로 설치하기"** 버튼 클릭
4. 홈 화면에 StockAI 아이콘 생성 완료 🎉

---

## ✅ PWA 기능

| 기능 | 지원 |
|------|------|
| 홈 화면 아이콘 | ✅ iOS + Android |
| 전체화면 (앱처럼) | ✅ |
| 오프라인 사용 | ✅ (캐시된 데이터) |
| 데이터 저장 | ✅ localStorage |
| 이미지 첨부 | ✅ |
| 자동 업데이트 | ✅ (코드 수정 후 push하면 자동 반영) |

---

## 🔄 업데이트 방법

1. `index.html` 수정
2. GitHub 저장소에 파일 다시 업로드 (또는 Edit)
3. 자동 배포 → 1~2분 후 앱에 반영
