const CART_STORAGE_KEY = "intellimf-admin-cart";

let memoryCart = [];
function loadCartItems() {
  try {
    const items = JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY) || '[]');
    return Array.isArray(items) ? items.filter(item => item && /^\d{1,12}$/.test(item.schemeCode) && typeof item.schemeName === 'string' && item.schemeName.length <= 500 && Number.isFinite(Number(item.amount)) && Number(item.amount) > 0 && ['Daily', 'Weekly', 'Bi-Weekly', 'Monthly'].includes(item.frequency) && /^\d{4}-\d{2}-\d{2}$/.test(item.startDate)).slice(0, 20) : [];
  } catch (_) { return memoryCart; }
}
function saveCartItems(items) {
  memoryCart = items;
  try { window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items)); } catch (_) { /* Current-page cart still works. */ }
}
function formatCurrency(amount) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount);
}
function cartElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function createCartItemElement(schemeCode, schemeName, amount = 5000, frequency = 'Monthly', startDate = '') {
  const wrapper = cartElement('div', 'cart-item');
  wrapper.dataset.schemeCode = schemeCode;
  const fields = { selected_schemes: schemeCode, [`amount_${schemeCode}`]: amount, [`frequency_${schemeCode}`]: frequency, [`start_date_${schemeCode}`]: startDate };
  Object.entries(fields).forEach(([name, value]) => {
    const input = document.createElement('input');
    input.type = 'hidden'; input.name = name; input.value = String(value);
    wrapper.append(input);
  });
  const top = cartElement('div', 'cart-item-top');
  const title = cartElement('div');
  title.append(cartElement('strong', '', schemeName), cartElement('small', '', `Scheme Code: ${schemeCode}`));
  const remove = cartElement('button', 'ghost-button compact-button remove-cart-item', 'Remove');
  remove.type = 'button'; remove.setAttribute('aria-label', `Remove ${schemeName}`);
  top.append(title, remove);
  const details = cartElement('div', 'cart-details');
  [['Amount:', formatCurrency(amount)], ['Frequency:', frequency], ['Start Date:', startDate]].forEach(([label, value]) => {
    const row = cartElement('div', 'detail-row');
    row.append(cartElement('span', 'detail-label', label), cartElement('span', 'detail-value', value));
    details.append(row);
  });
  wrapper.append(top, details);
  return wrapper;
}
function renderCartItems(container) {
  if (!container) return;
  container.replaceChildren();
  const items = loadCartItems();
  if (!items.length) {
    const empty = cartElement('div', 'empty-cart', 'No funds added yet. Visit fund search to build your basket.');
    empty.id = 'empty-cart'; container.append(empty);
  }
  items.forEach(item => container.append(createCartItemElement(item.schemeCode, item.schemeName, item.amount, item.frequency, item.startDate)));
}

function updateCartCount() {
  const items = loadCartItems();
  const cartCount = document.getElementById("cart-count");
  const cartCountPill = document.getElementById("cart-count-pill");
  const cartLinkCount = document.getElementById("cart-link-count");
  const cartTotal = document.getElementById("cart-total");

  let total = 0;
  items.forEach((item) => {
    total += parseFloat(item.amount || "0");
  });

  const countText = `${items.length} fund${items.length === 1 ? "" : "s"}`;
  if (cartCount) {
    cartCount.textContent = countText;
  }
  if (cartCountPill) {
    cartCountPill.textContent = countText;
  }
  if (cartLinkCount) {
    cartLinkCount.textContent = `${items.length}`;
  }
  if (cartTotal) {
    cartTotal.textContent = formatCurrency(total);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (window.adminCartConfig && window.adminCartConfig.clearCart) {
    saveCartItems([]);
  }

  const cartItemsContainer = document.getElementById("cart-items");
  const addModal = document.getElementById("add-cart-modal");
  const addModalSchemeName = document.getElementById("add-modal-scheme-name");
  const addModalSchemeCode = document.getElementById("add-modal-scheme-code");
  const addModalAmount = document.getElementById("add-modal-amount");
  const addModalFrequency = document.getElementById("add-modal-frequency");
  const addModalStartDate = document.getElementById("add-modal-start-date");
  const addModalSaveButton = document.getElementById("add-modal-save-button");
  const addModalCancelButton = document.getElementById("add-modal-cancel-button");
  const addModalCloseButton = document.getElementById("add-modal-close-button");
  const clearCartButton = document.getElementById("clear-cart-button");

  if (cartItemsContainer) {
    renderCartItems(cartItemsContainer);
  }

  let addingScheme = null;
  let modalOpener = null;
  let previousOverflow = "";

  const closeAddModal = () => {
    if (!addModal) {
      return;
    }
    if (!addModal.classList.contains("show")) return;
    addingScheme = null;
    document.body.style.overflow = previousOverflow;
    if (modalOpener) modalOpener.focus();
    addModal.classList.remove("show");
    addModal.setAttribute("aria-hidden", "true");
  };

  const openAddModal = (schemeCode, schemeName) => {
    if (!addModal || !addModalSchemeName || !addModalSchemeCode || !addModalAmount || !addModalFrequency || !addModalStartDate) {
      return;
    }
    modalOpener = document.activeElement;
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    addingScheme = { schemeCode, schemeName };
    addModalSchemeName.textContent = schemeName;
    addModalSchemeCode.textContent = `Scheme Code: ${schemeCode}`;
    addModalAmount.value = 5000;
    addModalFrequency.value = "Monthly";
    const today = new Date();
    addModalStartDate.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    addModal.classList.add("show");
    addModal.setAttribute("aria-hidden", "false");
    addModalAmount.focus();
  };

  const saveAddModal = () => {
    if (!addingScheme || !addModalAmount || !addModalFrequency || !addModalStartDate) {
      return;
    }

    const { schemeCode, schemeName } = addingScheme;
    const amount = parseFloat(addModalAmount.value || "0");
    const frequency = addModalFrequency.value;
    const startDate = addModalStartDate.value;

    if (!addModalAmount.reportValidity() || !addModalStartDate.reportValidity()) return;

    const items = loadCartItems().filter((item) => item.schemeCode !== schemeCode);
    if (items.length >= 20) { alert("A basket can contain up to 20 funds."); return; }
    items.push({ schemeCode, schemeName, amount, frequency, startDate });
    saveCartItems(items);

    if (cartItemsContainer) {
      renderCartItems(cartItemsContainer);
    }
    updateCartCount();
    closeAddModal();
  };

  document.querySelectorAll(".add-to-cart-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const schemeCode = button.dataset.schemeCode;
      const schemeName = button.dataset.schemeName;
      if (schemeCode && schemeName) {
        openAddModal(schemeCode, schemeName);
      }
    });
  });

  if (cartItemsContainer) {
    cartItemsContainer.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement) || !target.classList.contains("remove-cart-item")) {
        return;
      }

      const cartItem = target.closest(".cart-item");
      if (!cartItem) {
        return;
      }

      const items = loadCartItems().filter((item) => item.schemeCode !== cartItem.dataset.schemeCode);
      saveCartItems(items);
      renderCartItems(cartItemsContainer);
      updateCartCount();
    });
  }

  if (addModalSaveButton) {
    addModalSaveButton.addEventListener("click", saveAddModal);
  }
  if (addModalCancelButton) {
    addModalCancelButton.addEventListener("click", closeAddModal);
  }
  if (addModalCloseButton) {
    addModalCloseButton.addEventListener("click", closeAddModal);
  }
  if (addModal) {
    addModal.addEventListener("click", (event) => {
      if (event.target === addModal) {
        closeAddModal();
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === 'Tab' && addModal && addModal.classList.contains('show')) {
      const controls = [...addModal.querySelectorAll('button, input, select')].filter(element => !element.disabled && element.type !== 'hidden');
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    if (event.key === "Escape") {
      closeAddModal();
    }
  });

  if (clearCartButton) {
    clearCartButton.addEventListener("click", () => {
      saveCartItems([]);
      if (cartItemsContainer) {
        renderCartItems(cartItemsContainer);
      }
      updateCartCount();
    });
  }

  updateCartCount();
});
