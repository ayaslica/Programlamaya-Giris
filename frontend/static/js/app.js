const tabs = document.querySelectorAll('.tab-btn');
const sections = document.querySelectorAll('.tab');

function switchTab(tab) {
  sections.forEach(s => s.classList.add('hidden'));
  document.getElementById(tab).classList.remove('hidden');
}

tabs.forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.tab)));

async function loadPeriods(selectEl, timeframe) {
  const res = await fetch(`/api/v1/period-options/${timeframe}`);
  const data = await res.json();
  selectEl.innerHTML = data.periods.map(p => `<option>${p}</option>`).join('');
}

const analyzeTf = document.getElementById('analyzeTf');
const analyzePeriod = document.getElementById('analyzePeriod');
loadPeriods(analyzePeriod, analyzeTf.value);
analyzeTf.addEventListener('change', () => loadPeriods(analyzePeriod, analyzeTf.value));

document.getElementById('analyzeBtn').addEventListener('click', async () => {
  const payload = {
    symbol: document.getElementById('analyzeSymbol').value,
    timeframe: analyzeTf.value,
    period: analyzePeriod.value,
    debug: true,
  };
  const res = await fetch('/api/v1/analyze', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  document.getElementById('analyzeOut').textContent = JSON.stringify(await res.json(), null, 2);
});

document.getElementById('scanBtn').addEventListener('click', async () => {
  const payload = {
    symbols: document.getElementById('scanSymbols').value.split(',').map(s => s.trim()),
    timeframe: '1d',
    mode: document.getElementById('scanMode').value,
  };
  const res = await fetch('/api/v1/scan', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  document.getElementById('scanOut').textContent = JSON.stringify(await res.json(), null, 2);
});

document.getElementById('btBtn').addEventListener('click', async () => {
  const payload = {
    symbol: document.getElementById('btSymbol').value,
    timeframe: document.getElementById('btTf').value,
    min_score: Number(document.getElementById('btScore').value),
  };
  const res = await fetch('/api/v1/backtest', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  const m = data.metrics;
  const cards = [
    ['Toplam Getiri', `${m.total_return_pct}%`],
    ['Win Rate', `${m.win_rate_pct}%`],
    ['Toplam İşlem', `${m.total_trades}`],
    ['Profit Factor', `${m.profit_factor}`],
    ['Max DD', `${m.max_drawdown_pct}%`],
    ['Ort. Süre', `${m.avg_trade_duration_bars}`],
  ];
  document.getElementById('kpis').innerHTML = cards.map(([k,v]) => `<div class="bg-slate-900 p-3 rounded"><p class="text-xs text-slate-400">${k}</p><p class="font-semibold">${v}</p></div>`).join('');

  Plotly.newPlot('equityChart', [
    { y: data.equity_curve, type: 'scatter', name: 'Equity' },
    { y: data.buy_hold_curve, type: 'scatter', name: 'Buy & Hold' }
  ], { title: 'Equity Curve' }, {responsive: true});

  Plotly.newPlot('ddChart', [
    { y: data.drawdown_curve, type: 'scatter', fill: 'tozeroy', name: 'Drawdown' }
  ], { title: 'Drawdown' }, {responsive: true});

  document.getElementById('btOut').textContent = JSON.stringify(data.trades, null, 2);
});
