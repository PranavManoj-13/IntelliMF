(function () {
  const page = document.getElementById('public-basket-page');
  if (!page) return;
  const key = 'intellimf-public-basket';
  if (page.dataset.submitted === 'true') {
    try { sessionStorage.removeItem(key); } catch (_) { /* Optional draft storage. */ }
    return;
  }
  const container = document.getElementById('selected-funds');
  const status = document.getElementById('basket-selection-status');
  let funds = [];
  try {
    const saved = JSON.parse(sessionStorage.getItem(key) || '[]');
    if (Array.isArray(saved)) funds = saved.filter(item => item && /^\d{1,12}$/.test(item.code) && typeof item.name === 'string').slice(0, 20);
  } catch (_) { /* An empty draft is safe. */ }
  const checkboxes = [...document.querySelectorAll('.survey-select')];
  // The central selection owns POST fields; checkboxes remain a no-JS fallback.
  checkboxes.forEach(checkbox => checkbox.removeAttribute('name'));
  function render() {
    container.replaceChildren();
    if (!funds.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'Choose funds from the search results.';
      container.append(empty);
    }
    funds.forEach(fund => {
      const row = document.createElement('div');
      row.className = 'selected-fund';
      const name = document.createElement('span');
      name.textContent = fund.name;
      const input = document.createElement('input');
      input.type = 'hidden'; input.name = 'scheme_codes'; input.value = fund.code;
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'ghost-button compact-button'; remove.textContent = 'Remove';
      remove.setAttribute('aria-label', `Remove ${fund.name}`);
      remove.addEventListener('click', () => { funds = funds.filter(item => item.code !== fund.code); render(); });
      row.append(name, input, remove); container.append(row);
    });
    checkboxes.forEach(checkbox => { checkbox.checked = funds.some(fund => fund.code === checkbox.value); });
    status.textContent = `${funds.length} of 20 funds selected`;
    try { sessionStorage.setItem(key, JSON.stringify(funds)); } catch (_) { /* Current page selection still works. */ }
  }
  checkboxes.forEach(checkbox => checkbox.addEventListener('change', () => {
    if (checkbox.checked && !funds.some(fund => fund.code === checkbox.value)) {
      if (funds.length === 20) { checkbox.checked = false; status.textContent = 'You can select up to 20 funds.'; return; }
      funds.push({ code: checkbox.value, name: checkbox.dataset.name });
    } else funds = funds.filter(fund => fund.code !== checkbox.value);
    render();
  }));
  document.getElementById('basket-submit').addEventListener('submit', event => {
    if (!funds.length) { event.preventDefault(); status.textContent = 'Select at least one fund before submitting.'; }
  });
  render();
})();
