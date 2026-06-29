/**
 * sp500_auto_loader.js
 * ─────────────────────
 * GitHub Actions가 3일마다 data/sp500_latest.json 을 갱신하면
 * 이 스크립트가 자동으로 불러와 기존 S.spSnapshots 구조에 주입합니다.
 *
 * 사용법: index.html 맨 아래 </body> 직전에 아래 한 줄 추가
 *   <script src="./sp500_auto_loader.js"></script>
 *
 * 또는 index.html 안에 <script> 블록으로 붙여넣기 가능.
 */

(function () {
  // ── 설정 ────────────────────────────────────────────────────────
  // 본인 GitHub Pages 저장소에 맞게 수정하세요
  const JSON_URL = './data/sp500_latest.json';

  // 자동 로드 재시도 간격 (ms): showPage('sp500') 호출 전에 S가 초기화되길 기다림
  const POLL_MS = 300;
  const MAX_TRIES = 20;
  // ─────────────────────────────────────────────────────────────────

  let _loaded = false;   // 이미 로드했으면 중복 방지
  let _data = null;      // 받아온 JSON 캐시

  /** JSON 파일 한 번만 fetch */
  async function fetchAutoData() {
    try {
      const res = await fetch(JSON_URL + '?_t=' + Date.now(), { cache: 'no-store' });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  /**
   * JSON → S.spSnapshots 형식으로 변환 후 주입
   * 기존 수동 업로드 스냅샷과 병합 (중복 날짜는 자동 버전이 우선)
   */
  function injectIntoState(data) {
    if (!window.S || !Array.isArray(window.S.spSnapshots)) return false;

    // rankings 배열 → 기존 {rank, symbol, name, marketcap, price} 형식
    const rows = (data.rankings || []).map(r => ({
      rank: r.rank,
      symbol: r.symbol,
      name: r.name,
      marketcap: r.marketcap,
      price: r.price,
      country: 'USA',
    }));

    if (!rows.length) return false;

    const label = data.date_label || data.updated_at?.slice(0, 5) || 'AUTO';
    const autoSnap = {
      date: label,
      label: `🤖 ${label} (자동)`,
      data: rows,
      auto: true,          // 자동 수집 표시
    };

    // 같은 date label 스냅샷 제거 후 맨 앞에 삽입
    window.S.spSnapshots = window.S.spSnapshots.filter(s => s.date !== label);
    window.S.spSnapshots.unshift(autoSnap);

    // 최대 10개 유지
    if (window.S.spSnapshots.length > 10) {
      window.S.spSnapshots = window.S.spSnapshots.slice(0, 10);
    }

    // 연속 상승 종목도 전역에 저장 (배지/알림용)
    window.SP500_RISING = data.rising_stocks || [];
    window.SP500_UPDATED_AT = data.updated_at || '';

    return true;
  }

  /** S&P500 페이지가 활성화됐을 때 배너 표시 */
  function showAutoBanner(data) {
    const page = document.getElementById('page-sp500');
    if (!page) return;

    // 이미 배너 있으면 스킵
    if (document.getElementById('sp500-auto-banner')) return;

    const rising = (data.rising_stocks || []).slice(0, 5);
    const risingHTML = rising.length
      ? rising.map(r =>
          `<span style="display:inline-flex;align-items:center;gap:4px;
            background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.25);
            color:#10b981;border-radius:6px;padding:3px 9px;font-size:11px;font-weight:600;font-family:var(--mono)">
            📈 ${r.symbol} <span style="font-weight:400;color:var(--text2)">${r.rank_change_total > 0 ? '+' : ''}${-r.rank_change_total}위▲ → ${r.current_rank}위</span>
          </span>`
        ).join('')
      : '<span style="font-size:11px;color:var(--text3)">연속 상승 종목 없음 (스냅샷 2개 이상 필요)</span>';

    const banner = document.createElement('div');
    banner.id = 'sp500-auto-banner';
    banner.style.cssText = [
      'background:rgba(59,130,246,.07);border:1px solid rgba(59,130,246,.2);',
      'border-radius:10px;padding:12px 16px;margin-bottom:16px;',
    ].join('');
    banner.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <span style="font-size:12px;font-weight:600;color:var(--accent)">
          🤖 자동 수집 완료 &nbsp;
          <span style="font-weight:400;font-size:11px;color:var(--text3)">${data.updated_at || ''}</span>
        </span>
        <span style="font-size:11px;color:var(--text3)">상위 ${data.top_n || 100}위 · ${(data.rankings||[]).length}개 종목</span>
      </div>
      <div style="font-size:11px;color:var(--text2);margin-bottom:6px;font-weight:600">📊 연속 상승 종목</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">${risingHTML}</div>
    `;

    // 업로드 영역 바로 위에 삽입
    const uploadArea = page.querySelector('.sp-upload-area');
    if (uploadArea) {
      page.insertBefore(banner, uploadArea);
    } else {
      page.prepend(banner);
    }
  }

  /** 메인 로드 흐름 */
  async function load() {
    if (_loaded) return;

    _data = await fetchAutoData();
    if (!_data) {
      console.log('[SP500 Auto] data/sp500_latest.json 없음 — 수동 업로드 모드 유지');
      return;
    }

    console.log(`[SP500 Auto] 데이터 로드 성공: ${_data.updated_at}, 종목 ${(_data.rankings||[]).length}개`);

    // S 객체가 초기화될 때까지 폴링
    let tries = 0;
    const waitForS = setInterval(() => {
      tries++;
      if (window.S && Array.isArray(window.S.spSnapshots)) {
        clearInterval(waitForS);
        const ok = injectIntoState(_data);
        if (ok) {
          _loaded = true;
          console.log('[SP500 Auto] S.spSnapshots 주입 완료');

          // 현재 sp500 페이지가 활성화돼 있으면 즉시 배너 + 테이블 갱신
          const activePage = document.querySelector('.page.active');
          if (activePage && activePage.id === 'page-sp500') {
            showAutoBanner(_data);
            if (typeof window.renderSpSnapshots === 'function') renderSpSnapshots();
            if (typeof window.renderSpTable === 'function') {
              const activeTab = document.querySelector('.sp-tab.active');
              renderSpTable('all', activeTab);
            }
            if (typeof window.updateSpRankChart === 'function') updateSpRankChart();
          }
        }
      }
      if (tries >= MAX_TRIES) {
        clearInterval(waitForS);
        console.warn('[SP500 Auto] S 객체 초기화 대기 시간 초과');
      }
    }, POLL_MS);
  }

  // ── showPage 후킹: sp500 페이지 열릴 때마다 배너 표시 ──
  const _origShowPage = window.showPage;
  window.showPage = function (id, el) {
    if (typeof _origShowPage === 'function') _origShowPage(id, el);
    if (id === 'sp500' && _loaded && _data) {
      // 약간 딜레이 후 배너 (renderSpTable이 먼저 실행되도록)
      setTimeout(() => showAutoBanner(_data), 80);
    }
  };

  // ── DOM 준비 후 실행 ──
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }

})();
