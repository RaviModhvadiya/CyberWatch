// recursive option merge for apexcharts
CW.merge = (a, b) => {
  const out = Array.isArray(a) ? [...a] : { ...a };
  Object.keys(b).forEach((k) => {
    out[k] =
      b[k] &&
      typeof b[k] === "object" &&
      !Array.isArray(b[k]) &&
      a[k] &&
      typeof a[k] === "object"
        ? CW.merge(a[k], b[k])
        : b[k];
  });
  return out;
};

CW.charts = {};

// light theme defaults shared by every chart
CW.base = (type, height) => ({
  chart: {
    type,
    height,
    background: "transparent",
    fontFamily: "Public Sans, sans-serif",
    toolbar: { show: false },
    foreColor: "#667388",
    animations: { speed: 650, dynamicAnimation: { speed: 400 } },
    parentHeightOffset: 0,
  },
  colors: CW.palette,
  dataLabels: { enabled: false },
  theme: { mode: "light" },
  grid: {
    borderColor: "#eaeef5",
    strokeDashArray: 3,
    padding: { left: 6, right: 8 },
  },
  legend: {
    fontSize: "12.5px",
    markers: { size: 6, shape: "circle" },
    itemMargin: { horizontal: 8, vertical: 3 },
  },
  states: {
    hover: { filter: { type: "lighten", value: 0.06 } },
    active: { filter: { type: "none" } },
  },
  markers: { hover: { sizeOffset: 3 } },
  noData: {
    text: "No data yet",
    style: { color: "#667388", fontSize: "14px" },
  },
  tooltip: { theme: "light", fillSeriesColor: false },
});

// whole-number value axis with tidy tick steps
CW.intAxis = (values) => {
  const max = Math.max(1, ...values.flat().filter((v) => Number.isFinite(v)));
  const labels = { formatter: (v) => Math.round(v).toLocaleString() };
  if (max < 5)
    return {
      min: 0,
      max: max === 1 ? 2 : max,
      tickAmount: max === 1 ? 2 : max,
      decimalsInFloat: 0,
      labels,
    };
  const raw = max / 5,
    mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = Math.ceil(
    mag * [1, 1.5, 2, 2.5, 5, 7.5, 10].find((m) => m * mag >= raw),
  );
  return {
    min: 0,
    max: step * 5,
    tickAmount: 5,
    forceNiceScale: false,
    decimalsInFloat: 0,
    labels,
  };
};

// create a chart once and update it afterwards
CW.draw = (key, selector, options) => {
  const el = document.querySelector(selector);
  if (!el) return;
  if (CW.charts[key]) {
    CW.charts[key].updateOptions(options, false, true);
    return;
  }
  CW.charts[key] = new ApexCharts(el, options);
  CW.charts[key].render().then(() => el.classList.remove("loading"));
};

// navigate when a chart element is clicked
CW.go = (url) => ({
  chart: {
    events: {
      dataPointSelection: (e, ctx, cfg) => {
        const target = url(cfg.dataPointIndex);
        if (target) window.location.href = target;
      },
    },
  },
});

// dashboard charts and cards
CW.dashboard = (data, urls) => {
  const c = data.charts,
    ink = "#101828";
  document
    .querySelectorAll("[data-stat]")
    .forEach((el) => CW.count(el, data.cards[el.dataset.stat]));
  const level = document.getElementById("score-level-text");
  if (level) {
    level.textContent = data.score.label;
    level.parentElement.style.color = data.score.color;
  }

  CW.draw(
    "score",
    "#chart-score",
    CW.merge(CW.base("radialBar", 250), {
      series: [data.cards.attack_score],
      colors: [data.score.color],
      labels: ["Attack score"],
      plotOptions: {
        radialBar: {
          startAngle: -125,
          endAngle: 125,
          hollow: { size: "64%" },
          track: { background: "#eaeef5" },
          dataLabels: {
            name: { offsetY: 24, color: "#667388", fontSize: "13px" },
            value: {
              offsetY: -14,
              fontSize: "46px",
              fontWeight: 700,
              fontFamily: "Bricolage Grotesque",
              color: ink,
              formatter: (v) => Math.round(v),
            },
          },
        },
      },
      stroke: { lineCap: "round" },
    }),
  );

  CW.draw(
    "hourly",
    "#chart-hourly",
    CW.merge(CW.base("area", 290), {
      series: [{ name: "Failed logins", data: c.failed_per_hour.values }],
      colors: ["#ef4a2b"],
      xaxis: {
        categories: c.failed_per_hour.labels,
        tickAmount: 8,
        labels: {
          rotate: 0,
          formatter: (v) =>
            typeof v === "string" && v.length === 5 ? v.slice(0, 2) + "h" : v,
        },
        axisBorder: { show: false },
        axisTicks: { show: false },
        crosshairs: { stroke: { color: "#c3cbdb", dashArray: 3 } },
      },
      stroke: { curve: "smooth", width: 2.5 },
      fill: { type: "gradient", gradient: { opacityFrom: 0.28, opacityTo: 0 } },
      yaxis: CW.intAxis(c.failed_per_hour.values),
      markers: { size: 0, hover: { size: 5 } },
      responsive: [{ breakpoint: 640, options: { xaxis: { tickAmount: 4 } } }],
      ...CW.go(() => urls.entries + "?status=" + urls.failed),
    }),
  );

  CW.draw(
    "types",
    "#chart-types",
    CW.merge(CW.base("donut", 290), {
      series: c.attack_types.values,
      labels: c.attack_types.labels,
      legend: { position: "bottom" },
      stroke: { width: 3, colors: ["#fff"] },
      plotOptions: {
        pie: {
          expandOnClick: false,
          donut: {
            size: "62%",
            labels: {
              show: true,
              name: { fontSize: "13px" },
              value: {
                fontFamily: "Bricolage Grotesque",
                fontWeight: 700,
                fontSize: "26px",
                color: ink,
              },
              total: {
                show: true,
                label: "Alerts",
                color: "#667388",
                formatter: (w) =>
                  w.globals.seriesTotals
                    .reduce((a, b) => a + b, 0)
                    .toLocaleString(),
              },
            },
          },
        },
      },
      ...CW.go(
        (i) =>
          c.attack_types.keys[i] &&
          urls.alerts + "?type=" + c.attack_types.keys[i],
      ),
    }),
  );

  CW.draw(
    "ips",
    "#chart-ips",
    CW.merge(CW.base("bar", 290), {
      series: [{ name: "Alerts", data: c.top_ips.values }],
      colors: ["#2446e8"],
      xaxis: {
        categories: c.top_ips.labels,
        axisBorder: { show: false },
        axisTicks: { show: false },
        labels: { formatter: (v) => Math.round(v) },
        ...CW.intAxis(c.top_ips.values),
      },
      plotOptions: {
        bar: { horizontal: true, borderRadius: 4, barHeight: "58%" },
      },
      legend: { show: false },
      grid: {
        borderColor: "#eaeef5",
        xaxis: { lines: { show: true } },
        yaxis: { lines: { show: false } },
      },
      yaxis: {
        labels: { style: { fontFamily: "JetBrains Mono", fontSize: "11.5px" } },
      },
      ...CW.go(
        (i) =>
          c.top_ips.labels[i] &&
          urls.alerts + "?ip=" + encodeURIComponent(c.top_ips.labels[i]),
      ),
    }),
  );

  CW.draw(
    "split",
    "#chart-split",
    CW.merge(CW.base("donut", 290), {
      series: c.login_split.values,
      labels: c.login_split.labels,
      colors: ["#ef4a2b", "#12a67a"],
      legend: { position: "bottom" },
      stroke: { width: 3, colors: ["#fff"] },
      plotOptions: {
        pie: {
          expandOnClick: false,
          donut: {
            size: "66%",
            labels: {
              show: true,
              value: {
                fontFamily: "Bricolage Grotesque",
                fontWeight: 700,
                fontSize: "26px",
                color: ink,
              },
              total: {
                show: true,
                label: "Login events",
                fontSize: "13px",
                color: "#667388",
                formatter: (w) =>
                  w.globals.seriesTotals
                    .reduce((a, b) => a + b, 0)
                    .toLocaleString(),
              },
            },
          },
        },
      },
      ...CW.go((i) =>
        i === 0 ? urls.entries + "?status=" + urls.failed : null,
      ),
    }),
  );

  CW.draw(
    "trend",
    "#chart-trend",
    CW.merge(CW.base("line", 290), {
      series: [{ name: "Alerts", data: c.daily_trend.values }],
      colors: ["#2446e8"],
      xaxis: {
        categories: c.daily_trend.labels,
        axisBorder: { show: false },
        axisTicks: { show: false },
      },
      stroke: { curve: "straight", width: 3 },
      yaxis: CW.intAxis(c.daily_trend.values),
      dataLabels: {
        enabled: c.daily_trend.values.length <= 3,
        offsetY: -8,
        style: {
          fontFamily: "Bricolage Grotesque",
          fontWeight: 700,
          colors: ["#101828"],
        },
        background: { enabled: false },
      },
      markers: {
        size: 5,
        colors: ["#fff"],
        strokeColors: "#2446e8",
        strokeWidth: 3,
        hover: { size: 7 },
      },
    }),
  );
};

// admin overview charts
CW.admin = (c, urls) => {
  CW.draw(
    "statuses",
    "#chart-statuses",
    CW.merge(CW.base("donut", 270), {
      series: c.statuses.values,
      labels: c.statuses.labels,
      colors: ["#ef4a2b", "#2446e8", "#12a67a", "#8a95a8"],
      legend: { position: "bottom" },
      stroke: { width: 3, colors: ["#fff"] },
      plotOptions: {
        pie: {
          expandOnClick: false,
          donut: {
            size: "66%",
            labels: {
              show: true,
              value: {
                fontFamily: "Bricolage Grotesque",
                fontWeight: 700,
                fontSize: "26px",
                color: "#101828",
              },
              total: {
                show: true,
                label: "Alerts",
                color: "#667388",
                formatter: (w) =>
                  w.globals.seriesTotals
                    .reduce((a, b) => a + b, 0)
                    .toLocaleString(),
              },
            },
          },
        },
      },
      ...CW.go((i) => urls.alerts + "?status=" + c.statuses.keys[i]),
    }),
  );
  CW.draw(
    "severities",
    "#chart-severities",
    CW.merge(CW.base("bar", 270), {
      series: [{ name: "Alerts", data: c.severities.values }],
      xaxis: {
        categories: c.severities.labels.map(
          (s) => s[0].toUpperCase() + s.slice(1),
        ),
        axisBorder: { show: false },
        axisTicks: { show: false },
      },
      colors: ["#5f7aa8", "#d88a0b", "#e8651a", "#d92d20"],
      plotOptions: {
        bar: { borderRadius: 6, columnWidth: "46%", distributed: true },
      },
      legend: { show: false },
      yaxis: CW.intAxis(c.severities.values),
      ...CW.go((i) => urls.alerts + "?severity=" + c.severities.labels[i]),
    }),
  );
  CW.draw(
    "analysts",
    "#chart-analysts",
    CW.merge(CW.base("bar", 270), {
      series: [
        { name: "Open", data: c.analysts.open },
        { name: "Closed", data: c.analysts.closed },
      ],
      colors: ["#ef4a2b", "#12a67a"],
      xaxis: {
        categories: c.analysts.labels,
        axisBorder: { show: false },
        axisTicks: { show: false },
      },
      chart: { stacked: true },
      plotOptions: { bar: { borderRadius: 4, columnWidth: "38%" } },
      legend: { position: "top", horizontalAlign: "left" },
      yaxis: CW.intAxis(
        c.analysts.open.map((v, i) => v + c.analysts.closed[i]),
      ),
    }),
  );
  CW.draw(
    "uploads",
    "#chart-uploads",
    CW.merge(CW.base("area", 270), {
      series: [{ name: "Uploads", data: c.uploads.values }],
      colors: ["#2446e8"],
      stroke: { curve: "smooth", width: 2.5 },
      fill: { type: "gradient", gradient: { opacityFrom: 0.25, opacityTo: 0 } },
      xaxis: {
        categories: c.uploads.labels,
        axisBorder: { show: false },
        axisTicks: { show: false },
      },
      yaxis: CW.intAxis(c.uploads.values),
      markers: {
        size: c.uploads.values.length <= 2 ? 5 : 0,
        colors: ["#fff"],
        strokeColors: "#2446e8",
        strokeWidth: 3,
        hover: { size: 6 },
      },
    }),
  );
};

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("dash");
  if (root) {
    const urls = { ...root.dataset },
      stamp = document.getElementById("live-at"),
      dot = document.getElementById("live-dot");
    let updated = Date.now();
    const render = (data) => {
      CW.dashboard(data, urls);
      updated = Date.now();
      dot.classList.remove("stale");
    };
    const pull = () =>
      fetch(urls.url, { credentials: "same-origin" })
        .then((r) => {
          if (!r.ok) throw new Error(r.status);
          return r.json();
        })
        .then(render)
        .catch(() => dot.classList.add("stale"));
    render(JSON.parse(document.getElementById("dash-data").textContent));
    setInterval(pull, Number(urls.refresh) * 1000);
    setInterval(() => {
      const s = Math.round((Date.now() - updated) / 1000);
      stamp.textContent =
        s < 5
          ? "Updated just now"
          : s < 60
            ? `Updated ${s}s ago`
            : `Updated ${Math.floor(s / 60)}m ago`;
    }, 1000);
    document.getElementById("refresh-now")?.addEventListener("click", (e) => {
      const i = e.currentTarget.querySelector("i");
      i.style.transition = "transform .6s";
      i.style.transform = "rotate(360deg)";
      setTimeout(() => {
        i.style.transition = "none";
        i.style.transform = "";
      }, 650);
      pull();
    });
  }
  const admin = document.getElementById("admin-data");
  if (admin)
    CW.admin(JSON.parse(admin.textContent), {
      ...document.getElementById("admin-root").dataset,
    });
});
