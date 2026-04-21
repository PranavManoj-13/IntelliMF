function renderLineChart(canvasId, labels, datasets) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !labels.length) {
    return;
  }

  const existingChart = Chart.getChart(canvas);
  if (existingChart) {
    existingChart.destroy();
  }

  new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          position: "bottom"
        }
      },
      scales: {
        x: {
          grid: {
            display: false
          }
        },
        y: {
          beginAtZero: false
        }
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (!window.MFCharts) {
    return;
  }

  const navSeries = window.MFCharts.navChart || [];
  renderLineChart(
    "navChart",
    navSeries.map((item) => item.date),
    [
      {
        label: "NAV",
        data: navSeries.map((item) => item.nav),
        borderColor: "#215732",
        backgroundColor: "rgba(33, 87, 50, 0.12)",
        fill: true,
        pointRadius: 0,
        tension: 0.2
      }
    ]
  );

  const sipSeries = window.MFCharts.sipSeries || [];
  renderLineChart(
    "sipChart",
    sipSeries.map((item) => item.date),
    [
      {
        label: "Portfolio Value",
        data: sipSeries.map((item) => item.portfolio_value),
        borderColor: "#215732",
        backgroundColor: "rgba(33, 87, 50, 0.12)",
        fill: false,
        pointRadius: 0,
        tension: 0.18
      },
      {
        label: "Invested Amount",
        data: sipSeries.map((item) => item.invested_amount),
        borderColor: "#d79f44",
        backgroundColor: "rgba(215, 159, 68, 0.12)",
        fill: false,
        pointRadius: 0,
        tension: 0.18
      }
    ]
  );
});
