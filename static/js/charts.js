/* Graphiques Chart.js aux couleurs de FLEET MANAGER. Les données viennent toujours de Django (json_script). */
(function () {
  const PALETTE = ["#2563eb", "#0b1f3a", "#16a34a", "#d97706", "#ea580c", "#0284c7", "#7c3aed", "#94a3b8"];
  const STATUS_COLORS = {DISPONIBLE: "#16a34a", AFFECTE: "#2563eb", EN_ENTRETIEN: "#d97706", IMMOBILISE: "#ea580c", HORS_SERVICE: "#94a3b8"};
  const PRIORITY_COLORS = ["#0284c7", "#d97706", "#ea580c", "#dc2626"];

  Chart.defaults.font.family = "'Inter Variable', system-ui, sans-serif";
  Chart.defaults.color = "#64748b";
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;

  const fcfa = (v) => new Intl.NumberFormat("fr-FR").format(v) + " FCFA";
  const compact = (v) => new Intl.NumberFormat("fr-FR", {notation: "compact"}).format(v);

  function empty(canvas, labels, values) {
    if (!values.length || values.every((v) => !v)) {
      canvas.parentElement.innerHTML = '<div class="empty-state"><i class="bi bi-bar-chart"></i>Aucune donnée à afficher</div>';
      return true;
    }
    return false;
  }

  window.FleetCharts = {
    PALETTE, STATUS_COLORS, PRIORITY_COLORS,
    doughnut(id, labels, values, colors) {
      const canvas = document.getElementById(id);
      if (!canvas || empty(canvas, labels, values)) return;
      new Chart(canvas, {
        type: "doughnut",
        data: {labels, datasets: [{data: values, backgroundColor: colors || PALETTE, borderColor: "#fff", borderWidth: 2}]},
        options: {maintainAspectRatio: false, cutout: "66%", plugins: {legend: {position: "right"}}},
      });
    },
    bar(id, labels, values, opts = {}) {
      const canvas = document.getElementById(id);
      if (!canvas || empty(canvas, labels, values)) return;
      new Chart(canvas, {
        type: "bar",
        data: {labels, datasets: [{data: values, backgroundColor: opts.colors || "#2563eb", borderRadius: 6, maxBarThickness: 38}]},
        options: {
          maintainAspectRatio: false, indexAxis: opts.horizontal ? "y" : "x",
          plugins: {legend: {display: false}, tooltip: {callbacks: {label: (c) => opts.money ? fcfa(c.parsed[opts.horizontal ? "x" : "y"]) : c.formattedValue + (opts.unit || "")}}},
          scales: {
            [opts.horizontal ? "x" : "y"]: {beginAtZero: true, grid: {color: "#eef2f6"}, ticks: {callback: (v) => opts.money ? compact(v) : v, precision: 0}},
            [opts.horizontal ? "y" : "x"]: {grid: {display: false}},
          },
        },
      });
    },
    groupedBar(id, labels, datasets) {
      // datasets : [{label, values, color}] — ex. entretien et carburant par mois
      const canvas = document.getElementById(id);
      if (!canvas || empty(canvas, labels, datasets.flatMap((d) => d.values))) return;
      new Chart(canvas, {
        type: "bar",
        data: {labels, datasets: datasets.map((d) => ({label: d.label, data: d.values, backgroundColor: d.color, borderRadius: 5, maxBarThickness: 22}))},
        options: {
          maintainAspectRatio: false,
          plugins: {legend: {position: "top", align: "end"}, tooltip: {callbacks: {label: (c) => `${c.dataset.label} : ${fcfa(c.parsed.y)}`}}},
          scales: {y: {beginAtZero: true, grid: {color: "#eef2f6"}, ticks: {callback: (v) => compact(v)}}, x: {grid: {display: false}}},
        },
      });
    },
  };
})();
