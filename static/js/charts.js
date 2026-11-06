function renderLineChart(canvasId, labels, datasets) {
  if (typeof Chart === 'undefined') return;
  const style = getComputedStyle(document.documentElement);
  const ink = style.getPropertyValue('--muted').trim();
  const line = style.getPropertyValue('--line').trim();
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
          position: "bottom",
          labels: { color: ink, font: { family: "Inter, Arial, sans-serif", size: 11 }, usePointStyle: true, boxWidth: 6, padding: 20 }
        }
      },
      scales: {
        x: {
          ticks: { color: ink, maxTicksLimit: 7, font: { family: "Inter, Arial, sans-serif", size: 10 } },
          border: { color: line },
          grid: {
            display: false
          }
        },
        y: {
          beginAtZero: false,
          ticks: { color: ink, font: { family: "Inter, Arial, sans-serif", size: 10 } },
          border: { display: false },
          grid: { color: line }
        }
      }
    }
  });
}

function renderFundCharts() {
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
        borderColor: "#6987b4",
        backgroundColor: "rgba(105, 135, 180, 0.10)",
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
        borderColor: "#6987b4",
        backgroundColor: "rgba(105, 135, 180, 0.10)",
        fill: false,
        pointRadius: 0,
        tension: 0.18
      },
      {
        label: "Invested Amount",
        data: sipSeries.map((item) => item.invested_amount),
        borderColor: "#65a7a2",
        backgroundColor: "rgba(101, 167, 162, 0.10)",
        fill: false,
        pointRadius: 0,
        tension: 0.18
      }
    ]
  );
}
document.addEventListener("DOMContentLoaded", renderFundCharts);
