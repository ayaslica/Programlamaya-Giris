#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import itertools
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import yfinance as yf

from formuller import compute_indicators, _atr
from multi import analyze_trend_1d, analyze_setup_4h, combine_multi_tf
from ayrinti import (
    detect_breakout_setup,
    detect_support_resistance,
    detect_rejection_setup,
    detect_market_structure,
    detect_trend_engine,
    detect_price_channel,
    detect_divergences,
    compute_score,
    score_to_action,
    build_entry_plan,
    determine_entry_status,
    detect_structure_label,
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "backtest_sonuclar_ui"
OUTPUT_DIR.mkdir(exist_ok=True)

TECH_FILE = BASE_DIR / "Technology.txt"

BARS = 500
WARMUP = 60
COOLDOWN = 5
MAX_HOLD = 60

MIN_SAMPLE = 100

ATR_SL = 1.5
ATR_TP1 = 2.5
ATR_TP2 = 4.0

# Paralel worker sayısı — CPU/network dengesine göre ayarla
MAX_WORKERS = 8


@dataclass
class Snap:
    symbol:   str
    signal:   str
    ai:       str
    breakout: str
    mtf:      float
    trend1d:  str
    setup4h:  float
    rr:       float
    entry:    str
    yapi:     str
    result:   str
    pnl:      float
    win:      int
    loss:     int


@dataclass
class Filt:
    signal:      str
    ai:          str
    breakout:    str
    min_mtf:     float
    trend1d:     str
    min_setup4h: float
    min_rr:      float
    entry:       str
    yapi:        str

    def label(self) -> str:
        return (
            f"Sinyal={self.signal} | AI={self.ai} | Breakout={self.breakout} | "
            f"MinMTF={self.min_mtf} | Trend1D={self.trend1d} | "
            f"Setup4H>={self.min_setup4h} | RR>={self.min_rr} | "
            f"Entry={self.entry} | Yapi={self.yapi}"
        )


def load_symbols() -> list[str]:
    if not TECH_FILE.exists():
        return []
    lines = TECH_FILE.read_text(encoding="utf-8").splitlines()
    return [x.strip() for x in lines if x.strip() and not x.startswith("#")]


def fetch_df_1d(symbol: str, max_bars: int = BARS) -> pd.DataFrame | None:
    try:
        df = yf.download(symbol, period=f"{max_bars * 2}d", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 120:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna().tail(max_bars)
        return df if len(df) >= 120 else None
    except Exception:
        return None


def fetch_df_4h(symbol: str, max_bars: int = 500) -> pd.DataFrame | None:
    try:
        # Saat bazlı period yfinance'de desteklenmez; gün bazlı start/end kullan
        days_needed = min(730, max(90, (max_bars * 2) // 24 + 10))
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days_needed)

        df_1h = yf.download(
            symbol,
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            interval="1h",
            progress=False,
            auto_adjust=True,
        )
        if df_1h is None or df_1h.empty or len(df_1h) < 30:
            return None
        if isinstance(df_1h.columns, pd.MultiIndex):
            df_1h.columns = df_1h.columns.get_level_values(0)
        df_1h = df_1h.dropna()
        df_4h = df_1h.resample("4h").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }).dropna()
        df_4h = df_4h.tail(max_bars)
        return df_4h if len(df_4h) >= 30 else None
    except Exception:
        return None


def simulate_with_dynamic_sl(df_future: pd.DataFrame, entry: float,
                              support_level: float, atr: float,
                              tp1_mult: float = 2.5, tp2_mult: float = 4.0) -> tuple[str, float]:
    sl_candidate = support_level if support_level and support_level < entry else entry - atr * 0.8
    sl = max(0.01, sl_candidate)
    tp1 = entry + atr * tp1_mult
    tp2 = entry + atr * tp2_mult

    bars = df_future.iloc[:MAX_HOLD]
    if bars.empty:
        return "TIMEOUT", 0.0

    # Numpy vektörel — iterrows() döngüsü yok
    highs = bars["High"].to_numpy(dtype=float)
    lows  = bars["Low"].to_numpy(dtype=float)

    for idx in range(len(bars)):
        if lows[idx] <= sl:
            return "SL",  round((sl  - entry) / entry * 100, 3)
        if highs[idx] >= tp2:
            return "TP2", round((tp2 - entry) / entry * 100, 3)
        if highs[idx] >= tp1:
            return "TP1", round((tp1 - entry) / entry * 100, 3)

    last = float(bars["Close"].iloc[-1])
    return "TIMEOUT", round((last - entry) / entry * 100, 3)


def build_full_analysis(df: pd.DataFrame, symbol: str) -> dict:
    ind = compute_indicators(df)
    trend_engine = detect_trend_engine(df, {
        "ema20": ind.ema20, "ema50": ind.ema50, "sma200": ind.sma200,
        "adx": ind.adx, "atr": ind.atr
    })
    ind.trend = trend_engine.get("trend", ind.trend)
    ind.trend_strength = trend_engine.get("trend_strength", ind.trend_strength)
    indicators_dict = {
        "ema20": ind.ema20, "ema50": ind.ema50, "sma200": ind.sma200,
        "rsi14": ind.rsi14, "rsi21": ind.rsi21, "macd_hist": ind.macd_hist,
        "adx": ind.adx, "vwap_state": ind.vwap_state, "stoch_k": ind.stoch_k,
        "atr": ind.atr, "bb_pct": ind.bb_pct, "mfi": ind.mfi,
        "trend_strength": ind.trend_strength,
    }
    sr_data = detect_support_resistance(df, ind.atr)
    breakout_data = detect_breakout_setup(df, indicators_dict, sr_data)
    rejection_data = detect_rejection_setup(df, indicators_dict, sr_data)
    market_structure = detect_market_structure(df)
    channel_data = detect_price_channel(df, indicators_dict)
    divergences = detect_divergences(df)

    score = compute_score(indicators_dict, divergences, ind.trend, sr_data, ind.price,
                          breakout_data=breakout_data, rejection_data=rejection_data,
                          market_structure=market_structure)
    action = score_to_action(score)

    return {
        "symbol": symbol,
        "price": ind.price,
        "trend": ind.trend,
        "action": action,
        "score": score,
        "indicators": indicators_dict,
        "sr_data": sr_data,
        "breakout_data": breakout_data,
        "rejection_data": rejection_data,
        "market_structure": market_structure,
        "channel_data": channel_data,
        "divergences": divergences,
    }


def get_4h_analysis(df_4h: pd.DataFrame) -> dict:
    if df_4h is None or len(df_4h) < 30:
        return {}
    ind_4h = compute_indicators(df_4h)
    indicators_4h = {
        "rsi14": ind_4h.rsi14, "stoch_k": ind_4h.stoch_k, "macd_hist": ind_4h.macd_hist,
        "adx": ind_4h.adx, "vwap_state": ind_4h.vwap_state, "atr": ind_4h.atr,
        "trend_strength": ind_4h.trend_strength,
    }
    sr_4h = detect_support_resistance(df_4h, ind_4h.atr)
    breakout_4h = detect_breakout_setup(df_4h, indicators_4h, sr_4h)
    return {
        "indicators": indicators_4h,
        "trend": ind_4h.trend,
        "breakout": breakout_4h,
        "price": ind_4h.price,
    }


def collect_symbol(symbol: str, use_ready_filter: bool = True) -> list[Snap]:
    df_1d = fetch_df_1d(symbol)
    if df_1d is None:
        return []

    df_4h_full = fetch_df_4h(symbol, max_bars=800)
    if df_4h_full is None:
        df_4h_full = df_1d.copy()

    rows: list[Snap] = []
    last_signal_bar = -COOLDOWN

    # 4H analizini bir kere hesapla (her bar için tekrar hesaplanmıyor)
    analysis_4h_cache: dict[pd.Timestamp, dict] = {}

    for i in range(WARMUP, len(df_1d) - MAX_HOLD - 1):
        if i - last_signal_bar < COOLDOWN:
            continue

        window_1d = df_1d.iloc[: i + 1].copy()
        analysis_1d = build_full_analysis(window_1d, symbol)

        current_date = window_1d.index[-1]

        # 4H window — cache ile tekrar hesaplama
        if current_date not in analysis_4h_cache:
            mask_4h = df_4h_full.index <= current_date
            if not mask_4h.any():
                df_4h_window = df_4h_full
            else:
                df_4h_window = df_4h_full.loc[:current_date]
            if len(df_4h_window) < 10:
                df_4h_window = df_4h_full.tail(30)
            analysis_4h_cache[current_date] = get_4h_analysis(df_4h_window)

        analysis_4h = analysis_4h_cache[current_date]

        trend_1d_res = analyze_trend_1d(analysis_1d)
        setup_4h_res = analyze_setup_4h(analysis_4h) if analysis_4h else {"score": 0, "state": "weak"}
        combined = combine_multi_tf(trend_1d_res, setup_4h_res)

        signal = str(combined.get("signal", "WAIT"))
        mtf_score = float(combined.get("final_score", 0))
        trend1d = str(trend_1d_res.get("state", "neutral"))
        setup4h_score = float(setup_4h_res.get("score", 0))

        if signal not in ("BUY", "EARLY"):
            continue
        if signal == "BUY" and mtf_score < 55:
            continue

        sr = analysis_1d.get("sr_data", {})
        supports = sr.get("support_zones", [])
        nearest_support = supports[0] if supports else None
        atr = analysis_1d["indicators"].get("atr", 0)
        if atr is None or atr <= 0:
            atr = 0.02 * analysis_1d["price"] if analysis_1d["price"] else 1.0

        entry_price = analysis_1d["price"]
        if entry_price is None or entry_price <= 0:
            continue

        sl_candidate = nearest_support if nearest_support and nearest_support < entry_price else entry_price - atr * 0.8
        sl = max(0.01, sl_candidate)
        tp1 = entry_price + atr * ATR_TP1
        rr = round((tp1 - entry_price) / max(entry_price - sl, 1e-9), 2)

        risk_metrics_for_entry = {"rr_ratio": rr}
        entry_status_obj = determine_entry_status(
            analysis_1d["action"],
            analysis_1d["indicators"],
            analysis_1d.get("breakout_data", {}),
            analysis_1d.get("rejection_data", {}),
            analysis_1d.get("channel_data", {}),
            risk_metrics_for_entry
        )
        entry_status = entry_status_obj.get("status", "NOT_READY")

        if use_ready_filter and entry_status != "READY":
            continue

        structure_label = detect_structure_label(
            analysis_1d["trend"], analysis_1d.get("channel_data", {}),
            analysis_1d.get("breakout_data", {}), combined,
            analysis_1d["indicators"], analysis_1d.get("market_structure", {})
        )

        ai_signal = "BUY" if (signal == "BUY" and mtf_score >= 60 and
                              analysis_1d["indicators"].get("macd_hist", 0) > 0 and
                              analysis_1d["indicators"].get("adx", 0) >= 20) else "EARLY"

        is_breakout = analysis_1d.get("breakout_data", {}).get("is_breakout", False)
        breakout_str = "Var" if is_breakout else "Yok"

        future_df = df_1d.iloc[i + 1:]
        result, pnl = simulate_with_dynamic_sl(future_df, entry_price, nearest_support, atr, ATR_TP1, ATR_TP2)

        win = 1 if (result in ("TP1", "TP2") or (result == "TIMEOUT" and pnl > 0)) else 0
        loss = 1 if (result == "SL" or (result == "TIMEOUT" and pnl < 0)) else 0

        rows.append(
            Snap(
                symbol=symbol,
                signal=signal,
                ai=ai_signal,
                breakout=breakout_str,
                mtf=round(mtf_score, 2),
                trend1d=trend1d,
                setup4h=round(setup4h_score, 2),
                rr=rr,
                entry=entry_status,
                yapi=structure_label,
                result=result,
                pnl=round(pnl, 3),
                win=win,
                loss=loss,
            )
        )
        last_signal_bar = i

    return rows


def passes(r: Snap, f: Filt) -> bool:
    if f.signal   != "HEPSI"  and r.signal   != f.signal:   return False
    if f.ai       != "Hepsi"  and r.ai       != f.ai:       return False
    if f.breakout != "Hepsi"  and r.breakout != f.breakout: return False
    if r.mtf      <  f.min_mtf:                             return False
    if f.trend1d  != "Hepsi"  and r.trend1d  != f.trend1d:  return False
    if r.setup4h  <  f.min_setup4h:                         return False
    if r.rr       <  f.min_rr:                              return False
    if f.entry    != "Hepsi"  and r.entry    != f.entry:    return False
    if f.yapi     != "Hepsi"  and r.yapi     != f.yapi:     return False
    return True


def summarize(rows: list[Snap]) -> dict:
    wins = [r for r in rows if r.win]
    losses = [r for r in rows if r.loss]
    gross_win = sum(r.pnl for r in rows if r.pnl > 0)
    gross_loss = abs(sum(r.pnl for r in rows if r.pnl < 0))
    pf = round(gross_win / gross_loss, 2) if gross_loss else 99.0
    wr = round((len(wins) / max(len(wins) + len(losses), 1)) * 100, 1)
    avg_pnl = round(sum(r.pnl for r in rows) / len(rows), 2) if rows else 0.0
    score = round((wr * 0.50) + (pf * 0.30) + (avg_pnl * 0.20), 2)
    return {"n": len(rows), "wr": wr, "avg": avg_pnl, "pf": pf, "score": score}


def find_best_filters(rows: list[Snap]) -> list[dict]:
    """Pandas DataFrame üzerinde vektörel filtre — combo döngüsü çok daha hızlı."""
    if not rows:
        return []

    # Snap listesini DataFrame'e çevir
    df = pd.DataFrame([vars(r) for r in rows])

    filters = []
    combos = itertools.product(
        ["HEPSI", "BUY", "EARLY"],
        ["Hepsi", "BUY", "EARLY"],
        ["Hepsi", "Var", "Yok"],
        [0, 50, 55, 60, 65],
        ["Hepsi", "bullish", "neutral"],
        [0, 20, 30, 40],
        [0, 1.5, 2.0, 2.5],
        ["HEPSI", "READY", "WAIT_PULLBACK", "NOT_READY"],
        ["HEPSI", "YUKSELEN_ERKEN", "YUKSELEN_ORTA",
         "YUKSELEN_SON", "DUZELTME", "TEPKI", "DUSEN",
         "YATAY", "EARLY_BREAKOUT", "CONFIRMED_BREAKOUT"],
    )

    for c in combos:
        mask = pd.Series([True] * len(df), index=df.index)
        if c[0] != "HEPSI":    mask &= df["signal"]   == c[0]
        if c[1] != "Hepsi":    mask &= df["ai"]        == c[1]
        if c[2] != "Hepsi":    mask &= df["breakout"]  == c[2]
        if c[3] > 0:            mask &= df["mtf"]       >= c[3]
        if c[4] != "Hepsi":    mask &= df["trend1d"]   == c[4]
        if c[5] > 0:            mask &= df["setup4h"]   >= c[5]
        if c[6] > 0:            mask &= df["rr"]        >= c[6]
        if c[7] != "HEPSI":    mask &= df["entry"]     == c[7]
        if c[8] != "HEPSI":    mask &= df["yapi"]      == c[8]

        sel = df[mask]
        if len(sel) < MIN_SAMPLE:
            continue

        wins_n   = int(sel["win"].sum())
        losses_n = int(sel["loss"].sum())
        gw = float(sel.loc[sel["pnl"] > 0, "pnl"].sum())
        gl = float(abs(sel.loc[sel["pnl"] < 0, "pnl"].sum()))
        pf = round(gw / gl, 2) if gl else 99.0
        wr = round(wins_n / max(wins_n + losses_n, 1) * 100, 1)
        avg_pnl = round(float(sel["pnl"].mean()), 2)
        if avg_pnl <= 0:
            continue
        score = round((wr * 0.50) + (pf * 0.30) + (avg_pnl * 0.20), 2)

        f = Filt(signal=c[0], ai=c[1], breakout=c[2], min_mtf=c[3],
                 trend1d=c[4], min_setup4h=c[5], min_rr=c[6], entry=c[7], yapi=c[8])
        filters.append({
            "label": f.label(),
            "n": len(sel),
            "wr": wr,
            "avg": avg_pnl,
            "pf": pf,
            "score": score,
        })

    filters.sort(key=lambda x: (x["score"], x["wr"], x["pf"], x["avg"], x["n"]), reverse=True)
    return filters


def write_report(best: list[dict], total_rows: int, use_ready_filter: bool) -> Path:
    sector_name = TECH_FILE.stem
    path = OUTPUT_DIR / f"{sector_name}_OZET_{'READY_ONLY' if use_ready_filter else 'ALL_SIGNALS'}.txt"
    lines = [
        "═" * 90,
        f"EN IYI FILTRE ANALIZI - {sector_name}",
        f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Toplam trade snapshot: {total_rows}",
        f"Sadece READY sinyalleri: {'Evet' if use_ready_filter else 'Hayır'}",
        "═" * 90, ""
    ]
    if not best:
        lines.append("Uygun filtre bulunamadi.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
    lines += ["EN IYI 10 FILTRE", "─" * 90, ""]
    for i, b in enumerate(best[:10], 1):
        lines.append(f"{i}. SKOR {b['score']:.2f} | WIN %{b['wr']:.1f} | AVG {b['avg']:+.2f}% | PF {b['pf']:.2f} | N={b['n']}")
        lines.append(f"   {b['label']}\n")
    top = best[0]
    lines += [
        "SONUC - EN IYI FILTRE",
        "─" * 90,
        top["label"], "",
        f"Skor            : {top['score']:.2f}",
        f"WinRate Closed  : %{top['wr']:.1f}",
        f"AvgPnL          : {top['avg']:+.2f}%",
        f"Profit Factor   : {top['pf']:.2f}",
        f"Trade Count     : {top['n']}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_ml_analysis(rows: list) -> dict:
    try:
        from sklearn.tree import DecisionTreeClassifier, export_text
        from sklearn.model_selection import cross_val_score
    except ImportError:
        return {"error": "scikit-learn yuklu degil. pip install scikit-learn"}
    closed = [r for r in rows if r.result in ("TP1", "TP2", "SL")]
    if len(closed) < 50:
        return {"error": f"Yeterli kapali trade yok: {len(closed)}"}
    feature_names = [
        "mtf", "setup4h", "rr", "signal_buy", "ai_buy", "breakout_var",
        "trend1d_bullish", "entry_ready", "yapi_erken", "yapi_orta",
        "yapi_son", "yapi_breakout"
    ]
    X, y = [], []
    for r in closed:
        X.append([
            r.mtf, r.setup4h, r.rr,
            1 if r.signal == "BUY" else 0,
            1 if r.ai == "BUY" else 0,
            1 if r.breakout == "Var" else 0,
            1 if r.trend1d == "bullish" else 0,
            1 if r.entry == "READY" else 0,
            1 if r.yapi == "YUKSELEN_ERKEN" else 0,
            1 if r.yapi == "YUKSELEN_ORTA" else 0,
            1 if r.yapi == "YUKSELEN_SON" else 0,
            1 if r.yapi in ("EARLY_BREAKOUT", "CONFIRMED_BREAKOUT") else 0,
        ])
        y.append(1 if r.win else 0)
    X = np.array(X, dtype=float)
    y = np.array(y)
    clf = DecisionTreeClassifier(max_depth=4, min_samples_leaf=30, random_state=42)
    cv_scores = cross_val_score(clf, X, y, cv=5, scoring="accuracy")
    clf.fit(X, y)
    importances = sorted(zip(feature_names, clf.feature_importances_), key=lambda x: x[1], reverse=True)
    tree_rules = export_text(clf, feature_names=feature_names, max_depth=3)
    from sklearn.tree import _tree
    tree_ = clf.tree_
    best_leaves = []
    def recurse(node, depth, conditions):
        if tree_.feature[node] == _tree.TREE_UNDEFINED:
            vals = tree_.value[node][0]
            total = int(sum(vals))
            wins = int(vals[1]) if len(vals) > 1 else 0
            wr = round(wins / total * 100, 1) if total > 0 else 0
            if total >= 30 and wr >= 50:
                best_leaves.append({"conditions": list(conditions), "win_rate": wr, "n": total, "wins": wins})
            return
        feat = feature_names[tree_.feature[node]]
        thresh = round(tree_.threshold[node], 2)
        recurse(tree_.children_left[node], depth+1, conditions + [f"{feat} <= {thresh}"])
        recurse(tree_.children_right[node], depth+1, conditions + [f"{feat} >  {thresh}"])
    recurse(0, 0, [])
    best_leaves.sort(key=lambda x: (x["win_rate"], x["n"]), reverse=True)
    return {
        "cv_accuracy": round(float(cv_scores.mean()) * 100, 1),
        "cv_std": round(float(cv_scores.std()) * 100, 1),
        "total_closed": len(closed),
        "base_win_rate": round(sum(y) / len(y) * 100, 1),
        "importances": importances,
        "tree_rules": tree_rules,
        "best_leaves": best_leaves[:5],
    }


def write_ml_report(ml: dict, out_dir: Path, sector: str, use_ready_filter: bool) -> Path:
    suffix = "READY_ONLY" if use_ready_filter else "ALL_SIGNALS"
    path = out_dir / f"{sector}_ML_RAPOR_{suffix}.txt"
    if "error" in ml:
        path.write_text(f"ML HATA: {ml['error']}", encoding="utf-8")
        return path
    lines = [
        "=" * 70,
        f"ML ANALİZ RAPORU — {sector} (Sadece READY: {use_ready_filter})",
        "=" * 70, "",
        f"Cross-Val Doğruluk : %{ml['cv_accuracy']} ± {ml['cv_std']}",
        f"Ham Win Rate       : %{ml['base_win_rate']}  ({ml['total_closed']} kapalı trade)",
        "", "── EN ÖNEMLİ İNDİKATÖRLER ──"
    ]
    for feat, imp in ml["importances"]:
        if imp > 0.01:
            bar = "#" * int(imp * 50)
            lines.append(f"  {feat:<20} {imp:.3f}  {bar}")
    lines += ["", "── EN İYİ KARAR KURALLARI ──", ""]
    for i, leaf in enumerate(ml["best_leaves"], 1):
        lines.append(f"{i}. Win Rate: %{leaf['win_rate']} | N={leaf['n']} ({leaf['wins']} kazanan)")
        for cond in leaf["conditions"]:
            lines.append(f"   IF {cond}")
        lines.append("")
    lines += ["── KARAR AĞACI (ilk 3 seviye) ──", "", ml["tree_rules"]]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_mode(symbols: list[str], ready_mode: bool) -> tuple[list[Snap], list[dict]]:
    """Sembol analizini paralel thread pool ile çalıştırır."""
    mode_str = "READY_FILTER_ON" if ready_mode else "ALL_SIGNALS"
    print(f"\n{'='*50}\nMOD: {mode_str}\n{'='*50}")

    all_rows: list[Snap] = []
    total = len(symbols)
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_sym = {
            executor.submit(collect_symbol, sym, ready_mode): sym
            for sym in symbols
        }
        for future in as_completed(future_to_sym):
            sym = future_to_sym[future]
            completed += 1
            print(f"\r[{completed:4}/{total}] {sym:15} tamamlandi...", end="", flush=True)
            try:
                result = future.result()
                all_rows.extend(result)
            except Exception as e:
                pass  # Hatalı sembolü sessizce geç

    print(f"\nTamamlandi. Toplam trade snapshot: {len(all_rows)}")
    return all_rows


def main():
    sector_name = TECH_FILE.stem
    print(f"\nAUTO RUN: {sector_name.upper()} ANALIZ\n")
    print(f"Paralel worker sayisi: {MAX_WORKERS}")
    symbols = load_symbols()
    if not symbols:
        print(f"{TECH_FILE.name} bulunamadi veya bos.")
        return

    for ready_mode in [False, True]:
        all_rows = run_mode(symbols, ready_mode)

        best = find_best_filters(all_rows)
        out = write_report(best, len(all_rows), ready_mode)
        print(f"\nTXT RAPOR: {out}")
        if best:
            top = best[0]
            print("\nEN IYI FILTRE")
            print(top["label"])
            print(f"Skor: {top['score']:.2f} | WinRate: %{top['wr']:.1f} | AvgPnL: {top['avg']:+.2f}% | PF: {top['pf']:.2f} | N={top['n']}")
        print("\nML analizi basliyor (Decision Tree)...")
        ml = run_ml_analysis(all_rows)
        ml_out = write_ml_report(ml, OUTPUT_DIR, sector_name, ready_mode)
        print(f"ML RAPOR: {ml_out}")
        if "error" not in ml:
            print(f"CV Dogruluk  : %{ml['cv_accuracy']} (baz: %{ml['base_win_rate']})")
            if ml["best_leaves"]:
                print("\nEn iyi kural:")
                leaf = ml["best_leaves"][0]
                print(f"  Win Rate: %{leaf['win_rate']} | N={leaf['n']}")
                for cond in leaf["conditions"]:
                    print(f"  IF {cond}")


if __name__ == "__main__":
    main()