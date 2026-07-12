"""
sp500_fetch.py
──────────────
companiesmarketcap.com에서 미국 시가총액 순위 CSV를 다운로드하고,
이전 스냅샷과 비교해 연속 상승 종목을 감지한 뒤
data/ 폴더에 JSON으로 저장합니다.
 
저장 파일:
  data/sp500_latest.json     — 웹페이지가 직접 fetch하는 최신 순위 + 분석 결과
  data/snapshots/MM.DD.csv   — 날짜별 원본 CSV 스냅샷 보관
"""
 
import requests
import pandas as pd
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
 
# ── 설정 ──────────────────────────────────────────────────────────
CSV_URL = "https://companiesmarketcap.com/usa/largest-companies-in-the-usa-by-market-cap/?download=csv"
DATA_DIR = Path("data")
SNAPSHOT_DIR = DATA_DIR / "snapshots"
OUTPUT_FILE = DATA_DIR / "sp500_latest.json"
 
# 연속 상승 판정 기준: 최근 N개 스냅샷에서 모두 순위가 올라야 함
RISING_WINDOW = 2          # 직전 스냅샷 대비 상승
RISING_CONSECUTIVE = 2     # 연속 상승 횟수 (스냅샷 2개 = 6일치)
TOP_N = 500                # 상위 N위 이내 종목만 분석 (100 → 500으로 확대)
 
# KST 기준 오늘 날짜
KST = timezone(timedelta(hours=9))
today = datetime.now(KST)
date_label = today.strftime("%m.%d")   # 예: "06.29"
# ──────────────────────────────────────────────────────────────────
 
 
def download_csv() -> pd.DataFrame:
    """companiesmarketcap.com에서 CSV를 다운로드해 DataFrame으로 반환"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Referer": "https://companiesmarketcap.com/usa/largest-companies-in-the-usa-by-market-cap/",
    }
    print(f"[{date_label}] CSV 다운로드 중: {CSV_URL}")
    resp = requests.get(CSV_URL, headers=headers, timeout=30)
    resp.raise_for_status()
 
    # 임시 파일로 저장 후 pandas로 읽기
    tmp_path = DATA_DIR / "_tmp.csv"
    tmp_path.write_bytes(resp.content)
    df = pd.read_csv(tmp_path, encoding="utf-8-sig")
    tmp_path.unlink(missing_ok=True)
 
    print(f"  → {len(df)}개 종목 다운로드 완료")
    return df
 
 
def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼명 정규화 및 상위 TOP_N 필터링"""
    # companiesmarketcap CSV 컬럼: Rank, Name, Symbol, marketcap, price, ...
    col_map = {}
    for c in df.columns:
        cl = c.strip().lower()
        if cl in ("rank", "#"):
            col_map[c] = "rank"
        elif cl in ("name", "company"):
            col_map[c] = "name"
        elif cl in ("symbol", "ticker"):
            col_map[c] = "symbol"
        elif "marketcap" in cl or "market cap" in cl or "market_cap" in cl:
            col_map[c] = "marketcap"
        elif cl in ("price",):
            col_map[c] = "price"
    df = df.rename(columns=col_map)
 
    required = {"rank", "name", "symbol"}
    missing = required - set(df.columns)
    if missing:
        print(f"  ⚠ 컬럼 누락: {missing} — 실제 컬럼: {list(df.columns)}")
 
    df["rank"] = pd.to_numeric(df.get("rank", range(1, len(df)+1)), errors="coerce")
    df = df.dropna(subset=["rank"])
    df["rank"] = df["rank"].astype(int)
    df = df[df["rank"] <= TOP_N].copy()
    if len(df) < TOP_N:
        print(f"  ⚠ CSV에 {len(df)}개 종목만 있음 (요청한 상위 {TOP_N}위보다 적음) — 있는 만큼만 사용")
    df = df.sort_values("rank").reset_index(drop=True)
    return df
 
 
def load_snapshots() -> list[dict]:
    """snapshots/ 폴더에서 기존 스냅샷 목록을 날짜 오름차순으로 반환"""
    if not SNAPSHOT_DIR.exists():
        return []
    snaps = []
    for f in sorted(SNAPSHOT_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(f, encoding="utf-8-sig")
            df = normalize_df(df)
            snaps.append({"date": f.stem, "df": df})
        except Exception as e:
            print(f"  ⚠ 스냅샷 읽기 실패 {f.name}: {e}")
    return snaps
 
 
def detect_rising(snapshots: list[dict], current_df: pd.DataFrame) -> list[dict]:
    """
    연속 상승 종목 감지.
    snapshots: 과거 스냅샷 목록 (오름차순)
    current_df: 오늘 데이터
 
    반환: 연속 상승 종목 리스트
      [{ symbol, name, rank_history: [{date, rank}], rank_change_total }]
    """
    if len(snapshots) < RISING_CONSECUTIVE:
        print(f"  ℹ 스냅샷 부족 ({len(snapshots)}개) — 최소 {RISING_CONSECUTIVE}개 필요")
        return []
 
    # 최근 window 스냅샷 + 오늘 합치기
    all_snaps = snapshots[-(RISING_CONSECUTIVE):] + [{"date": date_label, "df": current_df}]
 
    # 종목별 순위 이력 구성
    symbol_history: dict[str, list] = {}
    for snap in all_snaps:
        for _, row in snap["df"].iterrows():
            sym = str(row.get("symbol", "")).strip().upper()
            name = str(row.get("name", "")).strip()
            rank = int(row.get("rank", 9999))
            if sym not in symbol_history:
                symbol_history[sym] = {"name": name, "history": []}
            symbol_history[sym]["history"].append({"date": snap["date"], "rank": rank})
 
    rising = []
    for sym, info in symbol_history.items():
        hist = info["history"]
        if len(hist) < RISING_CONSECUTIVE + 1:
            continue
        # 모든 연속 구간에서 순위가 낮아졌는지(= 숫자가 작아졌는지) 확인
        is_rising = all(
            hist[i + 1]["rank"] < hist[i]["rank"]
            for i in range(len(hist) - 1)
        )
        if is_rising:
            first_rank = hist[0]["rank"]
            last_rank = hist[-1]["rank"]
            rising.append({
                "symbol": sym,
                "name": info["name"],
                "current_rank": last_rank,
                "rank_change_total": first_rank - last_rank,   # 양수 = 상승폭
                "rank_history": hist,
            })
 
    # 상승폭 내림차순 정렬
    rising.sort(key=lambda x: x["rank_change_total"], reverse=True)
    print(f"  → 연속 상승 종목: {len(rising)}개")
    return rising
 
 
def build_output(current_df: pd.DataFrame, rising: list[dict], snapshots: list[dict]) -> dict:
    """웹페이지용 JSON 구조 생성"""
    # 현재 순위 전체 리스트
    rankings = []
    for _, row in current_df.iterrows():
        mcap_raw = row.get("marketcap", "")
        rankings.append({
            "rank": int(row.get("rank", 0)),
            "symbol": str(row.get("symbol", "")).strip().upper(),
            "name": str(row.get("name", "")).strip(),
            "marketcap": str(mcap_raw).strip() if pd.notna(mcap_raw) else "",
            "price": str(row.get("price", "")).strip() if pd.notna(row.get("price")) else "",
        })
 
    # 스냅샷 날짜 목록 (웹에서 드롭다운용)
    snap_dates = [s["date"] for s in snapshots] + [date_label]
 
    return {
        "updated_at": today.strftime("%Y-%m-%d %H:%M KST"),
        "date_label": date_label,
        "top_n": TOP_N,
        "rankings": rankings,
        "rising_stocks": rising,
        "snapshot_dates": snap_dates,
    }
 
 
def main():
    # 디렉토리 생성
    DATA_DIR.mkdir(exist_ok=True)
    SNAPSHOT_DIR.mkdir(exist_ok=True)
 
    # 1. 다운로드
    df_raw = download_csv()
    df = normalize_df(df_raw)
 
    # 2. 오늘 스냅샷 저장 (MM.DD.csv)
    snap_path = SNAPSHOT_DIR / f"{date_label}.csv"
    df_raw.to_csv(snap_path, index=False, encoding="utf-8-sig")
    print(f"  → 스냅샷 저장: {snap_path}")
 
    # 3. 기존 스냅샷 불러오기 (오늘 제외)
    snapshots = [s for s in load_snapshots() if s["date"] != date_label]
    print(f"  → 기존 스냅샷 {len(snapshots)}개 로드")
 
    # 4. 연속 상승 종목 감지
    rising = detect_rising(snapshots, df)
    for r in rising[:5]:
        print(f"    📈 {r['symbol']} ({r['name']}) — {r['rank_change_total']}계단 상승, 현재 {r['current_rank']}위")
 
    # 5. 최종 JSON 저장
    output = build_output(df, rising, snapshots)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 완료 → {OUTPUT_FILE}  ({len(df)}개 종목, 상승 {len(rising)}개)")
 
 
if __name__ == "__main__":
    main()
