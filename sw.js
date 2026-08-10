// StockAI Service Worker — 오프라인 지원 + 캐시 관리
const CACHE_NAME = 'stockai-v10';
const STATIC_ASSETS = [
  './index.html',
  './manifest.json',
  './icons/icon-192x192.png',
  './icons/icon-512x512.png',
  'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js',
  'https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&family=DM+Mono:wght@400;500&display=swap'
];

// 항상 네트워크를 우선 시도해야 하는 요청 (HTML 문서 = index.html)
// PWA로 설치된 앱은 이 부분이 캐시 우선이면 배포한 새 버전이 계속 반영되지 않는 문제가 있어
// 네트워크 우선으로 바꿔, 인터넷이 연결돼 있으면 항상 최신 파일을 받아오도록 한다.
function isNavigationRequest(request) {
  return request.mode === 'navigate' ||
    (request.destination === 'document') ||
    request.url.endsWith('/index.html') ||
    request.url.endsWith('/');
}

// 설치: 정적 자산 캐시
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS.filter(function(url) {
        // 외부 폰트/라이브러리는 실패해도 설치 진행
        return url.startsWith('./');
      }));
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

// 활성화: 이전 캐시 정리 + 열려있는 모든 클라이언트(탭/설치된 앱)를 즉시 새 버전이 제어하도록 함
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// fetch:
//   - HTML 문서(index.html) 요청: 네트워크 우선 → 실패(오프라인) 시에만 캐시 사용
//   - 그 외 정적 자산(아이콘/폰트/라이브러리 등): 기존처럼 캐시 우선 (속도 + 오프라인 지원)
self.addEventListener('fetch', function(e) {
  // Google Sheets API / Finnhub / Gemini는 항상 네트워크 (기존 동작 유지)
  if(e.request.url.includes('docs.google.com') ||
     e.request.url.includes('googleapis.com') ||
     e.request.url.includes('finnhub') ||
     e.request.url.includes('gemini')) {
    return; // 기본 fetch 동작
  }

  if(isNavigationRequest(e.request)) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' }).then(function(response) {
        if(response && response.status === 200) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) { cache.put(e.request, clone); });
        }
        return response;
      }).catch(function() {
        // 오프라인일 때만 캐시된 index.html로 폴백
        return caches.match(e.request).then(function(cached) {
          return cached || caches.match('./index.html');
        });
      })
    );
    return;
  }

  // 정적 자산: 캐시 우선, 없으면 네트워크
  e.respondWith(
    caches.match(e.request).then(function(cached) {
      if(cached) return cached;

      return fetch(e.request).then(function(response) {
        if(e.request.method === 'GET' && response.status === 200) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(e.request, clone);
          });
        }
        return response;
      }).catch(function() {
        if(e.request.destination === 'document') {
          return caches.match('./index.html');
        }
      });
    })
  );
});
