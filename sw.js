// StockAI Service Worker — 오프라인 지원 + 캐시 관리
const CACHE_NAME = 'stockai-v1';
const STATIC_ASSETS = [
  './index.html',
  './manifest.json',
  './icons/icon-192x192.png',
  './icons/icon-512x512.png',
  'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js',
  'https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&family=DM+Mono:wght@400;500&display=swap'
];

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

// 활성화: 이전 캐시 정리
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

// fetch: 캐시 우선, 실패 시 네트워크
self.addEventListener('fetch', function(e) {
  // Google Sheets API는 항상 네트워크
  if(e.request.url.includes('docs.google.com') ||
     e.request.url.includes('googleapis.com') ||
     e.request.url.includes('finnhub') ||
     e.request.url.includes('gemini')) {
    return; // 기본 fetch 동작
  }

  e.respondWith(
    caches.match(e.request).then(function(cached) {
      if(cached) return cached;

      return fetch(e.request).then(function(response) {
        // 성공한 GET 요청은 캐시에 저장
        if(e.request.method === 'GET' && response.status === 200) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(e.request, clone);
          });
        }
        return response;
      }).catch(function() {
        // 오프라인 시 index.html 반환
        if(e.request.destination === 'document') {
          return caches.match('./index.html');
        }
      });
    })
  );
});
