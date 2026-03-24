# FinAnalytica - Finansal Analiz ve Trading Sistemi

Profesyonel, sürdürülebilir ve genişletilebilir bir mimari ile geliştirilmiş FastAPI tabanlı analiz/backtest platformu.

## Mimari Özeti

- **API Katmanı (`app/api`)**: REST endpointleri (`/analyze`, `/scan`, `/backtest`), hata yönetimi ve OpenAPI.
- **Servis Katmanı (`app/services`)**: Veri çekme, indikatör hesaplama, divergence, kural motoru, scan, backtest.
- **Çekirdek Konfigürasyon (`app/core`)**: YAML + ENV override ile merkezi config yönetimi.
- **UI Katmanı (`frontend`)**: Mobile-first, sade ve profesyonel dashboard; Analyze/Scan/Backtest sekmeleri.
- **Yardımcı Katman (`app/utils`)**: rate limit, request-id, response-time middleware ve logging.

## Dizin Yapısı

```text
.
├── app
│   ├── api/v1/routes.py
│   ├── core/config.py
│   ├── main.py
│   ├── models/schemas.py
│   ├── services/
│   │   ├── analysis_service.py
│   │   ├── backtest_service.py
│   │   ├── cache_service.py
│   │   ├── data_service.py
│   │   ├── divergence_service.py
│   │   ├── indicator_service.py
│   │   ├── rule_engine.py
│   │   └── scan_service.py
│   └── utils/
│       ├── logging_setup.py
│       └── middleware.py
├── config/
│   ├── config.yaml
│   └── rules.json
├── frontend/
│   ├── index.html
│   └── static/js/app.js
├── tests/test_api.py
└── requirements.txt
```

## Özellikler

- OHLCV analizi (min 100 bar uyarısı)
- Timeframe: `1h`, `4h`, `1d` (+ dinamik period seçenekleri)
- Base currency formatı: `SYMBOL.BASE` (ör: `BTC.USDT`, `THYAO.IS`)
- Sepet analizi ve portföy modu (equal-weight daily rebalance)
- İndikatörler: RSI, MACD, VWAP, CVD, EMA/SMA, Ichimoku, Fibonacci, MFI, Volume Profile
- Divergence: regular/hidden, swing high/low + min distance
- Skorlama: `score = Σ(weight_i * factor_i)`
- Rule engine (JSON) + debug çıktısı
- Backtest: stop-loss, take-profit, trailing-stop, time-stop, reverse signal
- Risk yönetimi: `% risk` veya `fixed`
- Komisyon & slippage konfigürasyondan
- Cache katmanları (OHLCV, indikatör, backtest, scan)
- Rate limit: 60 req/min/IP

## Çalıştırma

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- UI: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

## Notlar

- Veri bulunamazsa API `404` döner ve öneri verir (örn. `THYAO.IS deneyin`).
- İnternet erişimi yoksa mevcut cache kullanımı hedeflenir.
- Backtest sonuçları parametre bazlı cache’lenir.
