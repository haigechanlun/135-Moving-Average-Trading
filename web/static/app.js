/* global LightweightCharts */

const state = {
  symbol: localStorage.getItem("njm135.symbol") || "BTCUSDT",
  interval: localStorage.getItem("njm135.interval") || "1d",
  exitMa: localStorage.getItem("njm135.exitMa") || "55",
  symbols: [],
  symbolSort: localStorage.getItem("njm135.symbolSort") || "volume",
  data: null,
  requestId: 0,
};

const $ = (selector) => document.querySelector(selector);
const els = {
  symbolList: $("#symbolList"),
  search: $("#symbolSearch"),
  symbolCount: $("#symbolCount"),
  sortVolume: $("#sortVolume"),
  sortChange: $("#sortChange"),
  chart: $("#chart"),
  loading: $("#chartLoading"),
  error: $("#chartError"),
  errorMessage: $("#errorMessage"),
  refresh: $("#refreshButton"),
  instrument: $("#instrumentSymbol"),
  icon: $("#coinIcon"),
  lastPrice: $("#lastPrice"),
  change: $("#priceChange"),
  exitMa: $("#exitMa"),
  patterns: $("#allPatterns"),
  showMa: $("#showMa"),
  showBoll: $("#showBoll"),
  showMacd: $("#showMacd"),
  macdPane: $("#macdPane"),
  macdChart: $("#macdChart"),
  signalBadge: $("#signalBadge"),
  signalTitle: $("#signalTitle"),
  signalDescription: $("#signalDescription"),
  signalCount: $("#signalCount"),
  lastUpdate: $("#lastUpdate"),
  barCount: $("#barCount"),
  signalTable: $("#signalTable"),
  marketStatus: $("#marketStatus"),
  toast: $("#toast"),
};

const formatPrice = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  const digits = n >= 1000 ? 2 : n >= 1 ? 4 : 6;
  return n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

const formatChange = (value) => {
  const n = Number(value || 0) * 100;
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
};

function sortedSymbols(items) {
  const copy = [...items];
  const missingChange = (item) => item.change24h == null;
  if (state.symbolSort === "change-desc") {
    copy.sort((a, b) => {
      if (missingChange(a) !== missingChange(b)) return missingChange(a) - missingChange(b);
      return Number(b.change24h) - Number(a.change24h);
    });
  } else if (state.symbolSort === "change-asc") {
    copy.sort((a, b) => {
      if (missingChange(a) !== missingChange(b)) return missingChange(a) - missingChange(b);
      return Number(a.change24h) - Number(b.change24h);
    });
  } else {
    copy.sort((a, b) => (b.quoteVolume || 0) - (a.quoteVolume || 0));
  }
  return copy;
}

function updateSortButtons() {
  const changeSort = state.symbolSort.startsWith("change");
  els.sortVolume.classList.toggle("active", !changeSort);
  els.sortChange.classList.toggle("active", changeSort);
  els.sortChange.innerHTML = changeSort
    ? `24h<span class="arrow">${state.symbolSort === "change-desc" ? "↓" : "↑"}</span>`
    : "24h";
}

const toast = (message) => {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 2200);
};

const chartOptions = {
  layout: {
    background: { color: "#0b0f16" },
    textColor: "#78849a",
    fontFamily: "DM Mono, monospace",
    fontSize: 10,
  },
  grid: {
    vertLines: { color: "#18202c" },
    horzLines: { color: "#18202c" },
  },
  crosshair: {
    mode: LightweightCharts.CrosshairMode.Normal,
    vertLine: { color: "#67748b88", style: 2, labelBackgroundColor: "#334155" },
    horzLine: { color: "#67748b88", style: 2, labelBackgroundColor: "#334155" },
  },
  rightPriceScale: {
    borderColor: "#273143",
    scaleMargins: { top: 0.06, bottom: 0.23 },
    // 主图与副图刻度宽度必须一致，否则绘图区宽度不同，同一根 K 线会落在不同横坐标。
    minimumWidth: 72,
  },
  timeScale: {
    borderColor: "#273143",
    timeVisible: true,
    secondsVisible: false,
    rightOffset: 5,
    barSpacing: 7,
    minBarSpacing: 2,
  },
  localization: { locale: "zh-CN" },
};

const chart = LightweightCharts.createChart(els.chart, chartOptions);
const macdChart = LightweightCharts.createChart(els.macdChart, {
  ...chartOptions,
  rightPriceScale: { borderColor: "#273143", scaleMargins: { top: 0.18, bottom: 0.08 }, minimumWidth: 72 },
  timeScale: { ...chartOptions.timeScale, visible: true },
});

const candleSeries = chart.addCandlestickSeries({
  upColor: "#2dd4a7",
  downColor: "#ff6678",
  borderUpColor: "#2dd4a7",
  borderDownColor: "#ff6678",
  wickUpColor: "#2dd4a7",
  wickDownColor: "#ff6678",
  priceLineVisible: true,
  lastValueVisible: true,
});
const volumeSeries = chart.addHistogramSeries({
  priceFormat: { type: "volume" },
  priceScaleId: "volume",
  lastValueVisible: false,
  priceLineVisible: false,
});
chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.83, bottom: 0 } });

const ma13Series = chart.addLineSeries({
  color: "#f6a94a", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "MA13",
});
const ma34Series = chart.addLineSeries({
  color: "#4ea1ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "MA34",
});
const ma55Series = chart.addLineSeries({
  color: "#a78bfa", lineWidth: 2, priceLineVisible: false, lastValueVisible: false, title: "MA55",
});
const bollUpperSeries = chart.addLineSeries({
  color: "#5eead4", lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed,
  priceLineVisible: false, lastValueVisible: false, title: "BOLL上",
});
const bollMidSeries = chart.addLineSeries({
  color: "#94a3b8", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "BOLL中",
});
const bollLowerSeries = chart.addLineSeries({
  color: "#5eead4", lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed,
  priceLineVisible: false, lastValueVisible: false, title: "BOLL下",
});
const macdHistSeries = macdChart.addHistogramSeries({
  lastValueVisible: false, priceLineVisible: false, title: "MACD",
});
const macdDifSeries = macdChart.addLineSeries({
  color: "#f6a94a", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "DIF",
});
const macdDeaSeries = macdChart.addLineSeries({
  color: "#4ea1ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "DEA",
});

const storedFlag = (key, fallback = true) => {
  const value = localStorage.getItem(`njm135.show.${key}`);
  return value == null ? fallback : value === "1";
};
els.showMa.checked = storedFlag("ma");
els.showBoll.checked = storedFlag("boll");
els.showMacd.checked = storedFlag("macd");

new ResizeObserver((entries) => {
  const box = entries[0].contentRect;
  chart.applyOptions({ width: box.width, height: box.height });
}).observe(els.chart);
new ResizeObserver((entries) => {
  const box = entries[0].contentRect;
  macdChart.applyOptions({ width: box.width, height: box.height });
}).observe(els.macdChart);

let syncingRange = false;
const bindRangeSync = (source, target) => {
  source.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (syncingRange || !range || !els.showMacd.checked) return;
    syncingRange = true;
    target.timeScale().setVisibleLogicalRange(range);
    syncingRange = false;
  });
};
bindRangeSync(chart, macdChart);
bindRangeSync(macdChart, chart);

const mapPoints = (points) => new Map((points || []).map((item) => [String(item.time), item.value]));

function setLegend(candle, time) {
  if (!candle) return;
  $("#legendOpen").textContent = formatPrice(candle.open);
  $("#legendHigh").textContent = formatPrice(candle.high);
  $("#legendLow").textContent = formatPrice(candle.low);
  $("#legendClose").textContent = formatPrice(candle.close);
  const key = String(time);
  $("#legendMa13").textContent = formatPrice(state.maMaps?.["13"].get(key));
  $("#legendMa34").textContent = formatPrice(state.maMaps?.["34"].get(key));
  $("#legendMa55").textContent = formatPrice(state.maMaps?.["55"].get(key));
  $("#legendBollMid").textContent = formatPrice(state.bollMaps?.mid.get(key));
  $("#legendMacdDif").textContent = formatPrice(state.macdMaps?.dif.get(key));
  $("#legendMacdDea").textContent = formatPrice(state.macdMaps?.dea.get(key));
  $("#legendMacdHist").textContent = formatPrice(state.macdMaps?.hist.get(key));
}

const moveLegend = (param) => {
  if (!param.time || !param.seriesData) {
    if (state.data?.candles.length) {
      const last = state.data.candles.at(-1);
      setLegend(last, last.time);
    }
    return;
  }
  const candle = param.seriesData.get(candleSeries) || state.data?.candles.find((item) => item.time === param.time);
  setLegend(candle, param.time);
};
chart.subscribeCrosshairMove(moveLegend);
macdChart.subscribeCrosshairMove(moveLegend);

function applyOverlays(data = state.data) {
  if (!data) return;
  const showMa = els.showMa.checked;
  const showBoll = els.showBoll.checked;
  const showMacd = els.showMacd.checked;
  ma13Series.setData(showMa ? data.ma["13"] : []);
  ma34Series.setData(showMa ? data.ma["34"] : []);
  ma55Series.setData(showMa ? data.ma["55"] : []);
  bollUpperSeries.setData(showBoll ? data.boll.upper : []);
  bollMidSeries.setData(showBoll ? data.boll.mid : []);
  bollLowerSeries.setData(showBoll ? data.boll.lower : []);
  document.querySelectorAll(".legend-ma").forEach((el) => el.classList.toggle("hidden", !showMa));
  document.querySelectorAll(".legend-boll").forEach((el) => el.classList.toggle("hidden", !showBoll));
  els.macdPane.classList.toggle("hidden", !showMacd);
  chart.applyOptions({ timeScale: { visible: !showMacd, borderColor: "#273143" } });
  if (showMacd) {
    macdHistSeries.setData(data.macd.hist);
    macdDifSeries.setData(data.macd.dif);
    macdDeaSeries.setData(data.macd.dea);
    requestAnimationFrame(() => {
      const range = chart.timeScale().getVisibleLogicalRange();
      if (range) macdChart.timeScale().setVisibleLogicalRange(range);
    });
  } else {
    macdHistSeries.setData([]);
    macdDifSeries.setData([]);
    macdDeaSeries.setData([]);
  }
}

function renderChart(data) {
  candleSeries.setData(data.candles);
  volumeSeries.setData(data.volume);
  candleSeries.setMarkers(els.patterns.checked ? data.patternMarkers : data.strategyMarkers);
  state.maMaps = Object.fromEntries(
    Object.entries(data.ma).map(([key, values]) => [key, mapPoints(values)]),
  );
  state.bollMaps = {
    mid: mapPoints(data.boll.mid),
    upper: mapPoints(data.boll.upper),
    lower: mapPoints(data.boll.lower),
  };
  state.macdMaps = {
    dif: mapPoints(data.macd.dif),
    dea: mapPoints(data.macd.dea),
    hist: mapPoints(data.macd.hist),
  };
  applyOverlays(data);
  const last = data.candles.at(-1);
  setLegend(last, last.time);
  chart.timeScale().fitContent();
  if (data.candles.length > 260) {
    chart.timeScale().setVisibleLogicalRange({ from: data.candles.length - 260, to: data.candles.length + 5 });
  }
}

function renderInstrument(data) {
  const base = data.symbol.replace(/USDT$/, "");
  els.instrument.textContent = `${base} / USDT`;
  els.icon.textContent = base.slice(0, 1);
  els.lastPrice.textContent = formatPrice(data.meta.lastClose);
  els.change.textContent = formatChange(data.meta.change);
  els.change.className = data.meta.change > 0 ? "positive" : data.meta.change < 0 ? "negative" : "neutral";
  els.signalCount.textContent = data.strategyMarkers.length;
  els.barCount.textContent = `${data.meta.bars} 根已完成 K 线`;
  els.lastUpdate.textContent = new Date(data.meta.lastTime * 1000).toLocaleDateString("zh-CN", {
    month: "2-digit", day: "2-digit", hour: ["1h", "4h"].includes(data.interval) ? "2-digit" : undefined,
  });

  const signal = data.meta.signal;
  els.signalBadge.className = `signal-badge ${signal}`;
  els.signalBadge.textContent = signal === "buy" ? "买入" : signal === "sell" ? "卖出" : "观察";
  const names = data.meta.patterns.join(" · ");
  els.signalTitle.textContent = names || (signal === "hold" ? "暂无交易信号" : "135 策略信号");
  els.signalDescription.textContent =
    signal === "hold" ? "等待最新一根 K 线收盘确认" : `信号已在 ${new Date(data.meta.lastTime * 1000).toLocaleDateString("zh-CN")} 收盘确认`;
}

function renderSignalLog(markers) {
  const rows = [...markers].reverse().slice(0, 12);
  if (!rows.length) {
    els.signalTable.innerHTML = '<div class="empty-row">当前范围内没有策略信号</div>';
    return;
  }
  const prices = new Map(state.data.candles.map((item) => [item.time, item.close]));
  els.signalTable.innerHTML = rows.map((marker) => {
    const buy = marker.shape === "arrowUp";
    const date = new Date(marker.time * 1000).toLocaleDateString("zh-CN", {
      year: "numeric", month: "2-digit", day: "2-digit",
    });
    return `
      <div class="signal-row">
        <time>${date}</time>
        <span class="signal-type ${buy ? "buy" : "sell"}">${buy ? "买入" : "卖出"}</span>
        <span>${marker.text || "135 信号"}</span>
        <span class="signal-price">${formatPrice(prices.get(marker.time))} USDT</span>
      </div>`;
  }).join("");
}

async function loadChart({ notify = false } = {}) {
  const requestId = ++state.requestId;
  els.loading.classList.remove("hidden");
  els.error.classList.add("hidden");
  els.refresh.classList.add("spinning");
  try {
    const query = new URLSearchParams({
      symbol: state.symbol,
      interval: state.interval,
      exitMa: state.exitMa,
      limit: state.interval === "1w" ? "400" : "700",
    });
    const response = await fetch(`/api/chart?${query}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "行情请求失败");
    if (requestId !== state.requestId) return;
    state.data = payload;
    renderChart(payload);
    renderInstrument(payload);
    renderSignalLog(payload.strategyMarkers);
    document.title = `${state.symbol.replace("USDT", "")} ${state.interval} · 135 Signal Desk`;
    localStorage.setItem("njm135.symbol", state.symbol);
    localStorage.setItem("njm135.interval", state.interval);
    localStorage.setItem("njm135.exitMa", state.exitMa);
    els.marketStatus.classList.remove("offline");
    if (notify) toast("行情已更新");
  } catch (error) {
    if (requestId !== state.requestId) return;
    els.errorMessage.textContent = error.message;
    els.error.classList.remove("hidden");
    els.marketStatus.classList.add("offline");
  } finally {
    if (requestId === state.requestId) {
      els.loading.classList.add("hidden");
      els.refresh.classList.remove("spinning");
    }
  }
}

function renderSymbols(filter = "") {
  const keyword = filter.trim().toUpperCase();
  const items = sortedSymbols(state.symbols).filter((item) =>
    item.symbol.includes(keyword) || item.base.includes(keyword) || item.name.toUpperCase().includes(keyword)
  );
  updateSortButtons();
  if (els.symbolCount) {
    els.symbolCount.textContent = `${state.symbols.length}`;
  }
  els.symbolList.innerHTML = items.map((item) => {
    const change = Number(item.change24h);
    const klass = change > 0 ? "positive" : change < 0 ? "negative" : "neutral";
    return `
      <button class="symbol-row ${item.symbol === state.symbol ? "active" : ""}" data-symbol="${item.symbol}">
        <span class="mini-icon">${item.base.slice(0, 1)}</span>
        <span class="symbol-meta"><strong>${item.base}</strong><small>${item.lastPrice == null ? "USDT 永续" : formatPrice(item.lastPrice)}</small></span>
        <span class="change ${klass}">${item.change24h == null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(1)}%`}</span>
      </button>`;
  }).join("") || '<div class="empty-row">没有匹配的币种</div>';
}

async function loadSymbols() {
  try {
    const response = await fetch("/api/symbols");
    const payload = await response.json();
    state.symbols = payload.items || [];
    renderSymbols();
  } catch {
    els.symbolList.innerHTML = '<div class="empty-row">币种列表加载失败</div>';
  }
}

els.symbolList.addEventListener("click", (event) => {
  const row = event.target.closest("[data-symbol]");
  if (!row || row.dataset.symbol === state.symbol) return;
  state.symbol = row.dataset.symbol;
  renderSymbols(els.search.value);
  loadChart();
});
els.search.addEventListener("input", () => renderSymbols(els.search.value));
els.sortVolume.addEventListener("click", () => {
  state.symbolSort = "volume";
  localStorage.setItem("njm135.symbolSort", state.symbolSort);
  renderSymbols(els.search.value);
});
els.sortChange.addEventListener("click", () => {
  state.symbolSort = state.symbolSort === "change-desc" ? "change-asc" : "change-desc";
  localStorage.setItem("njm135.symbolSort", state.symbolSort);
  renderSymbols(els.search.value);
});
document.querySelectorAll("[data-interval]").forEach((button) => {
  button.classList.toggle("active", button.dataset.interval === state.interval);
  button.addEventListener("click", () => {
    if (button.dataset.interval === state.interval) return;
    state.interval = button.dataset.interval;
    document.querySelectorAll("[data-interval]").forEach((item) =>
      item.classList.toggle("active", item === button)
    );
    loadChart();
  });
});
els.exitMa.value = state.exitMa;
els.exitMa.addEventListener("change", () => {
  state.exitMa = els.exitMa.value;
  loadChart();
});
els.patterns.addEventListener("change", () => {
  if (!state.data) return;
  candleSeries.setMarkers(els.patterns.checked ? state.data.patternMarkers : state.data.strategyMarkers);
  toast(els.patterns.checked ? "已显示全部 135 形态" : "仅显示策略买卖信号");
});
const persistOverlay = (key, checked) => {
  localStorage.setItem(`njm135.show.${key}`, checked ? "1" : "0");
  applyOverlays();
};
els.showMa.addEventListener("change", () => persistOverlay("ma", els.showMa.checked));
els.showBoll.addEventListener("change", () => persistOverlay("boll", els.showBoll.checked));
els.showMacd.addEventListener("change", () => persistOverlay("macd", els.showMacd.checked));
els.refresh.addEventListener("click", () => loadChart({ notify: true }));
$("#retryButton").addEventListener("click", () => loadChart());

loadSymbols();
loadChart();
