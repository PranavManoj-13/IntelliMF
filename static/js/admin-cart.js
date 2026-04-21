const CART_STORAGE_KEY = "intellimf-admin-cart";

function loadCartItems() {
  try {
    return JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY) || "[]");
  } catch (error) {
    return [];
  }
}

function saveCartItems(items) {
  window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items));
}

function formatCurrency(amount) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function createCartItemElement(schemeCode, schemeName, amount = 5000, frequency = "Monthly", startDate = "") {
  const wrapper = document.createElement("div");
  wrapper.className = "cart-item";
  wrapper.dataset.schemeCode = schemeCode;
  wrapper.innerHTML = `
    <input type="hidden" name="selected_schemes" value="${schemeCode}|||${schemeName}">
    <div class="cart-item-top">
      <div>
        <strong>${schemeName}</strong>
        <small>Scheme Code: ${schemeCode}</small>
      </div>
      <button type="button" class="ghost-button compact-button remove-cart-item">Remove</button>
    </div>
    <div class="cart-details">
      <div class="detail-row">
        <span class="detail-label">Amount:</span>
        <span class="detail-value">₹${Number(amount).toLocaleString("en-IN")}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Frequency:</span>
        <span class="detail-value">${frequency}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Start Date:</span>
        <span class="detail-value">${startDate}</span>
      </div>
    </div>
    <input type="hidden" name="amount_${schemeCode}" value="${amount}">
    <input type="hidden" name="frequency_${schemeCode}" value="${frequency}">
    <input type="hidden" name="start_date_${schemeCode}" value="${startDate}">
  `;
  return wrapper;
}

function renderCartItems(container) {
  if (!container) {
    return;
  }
  container.innerHTML = "";
  loadCartItems().forEach((item) => {
    container.appendChild(
      createCartItemElement(item.schemeCode, item.schemeName, item.amount, item.frequency, item.startDate),
    );
  });
}

function updateCartCount() {
  const items = loadCartItems();
  const cartCount = document.getElementById("cart-count");
  const cartCountPill = document.getElementById("cart-count-pill");
  const cartLinkCount = document.getElementById("cart-link-count");
  const cartTotal = document.getElementById("cart-total");
  const emptyCart = document.getElementById("empty-cart");

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
  if (emptyCart) {
    emptyCart.style.display = items.length ? "none" : "block";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (window.adminCartConfig && window.adminCartConfig.clearCart) {
    window.localStorage.removeItem(CART_STORAGE_KEY);
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

  const closeAddModal = () => {
    if (!addModal) {
      return;
    }
    addingScheme = null;
    addModal.classList.remove("show");
    addModal.setAttribute("aria-hidden", "true");
  };

  const openAddModal = (schemeCode, schemeName) => {
    if (!addModal || !addModalSchemeName || !addModalSchemeCode || !addModalAmount || !addModalFrequency || !addModalStartDate) {
      return;
    }
    addingScheme = { schemeCode, schemeName };
    addModalSchemeName.textContent = schemeName;
    addModalSchemeCode.textContent = `Scheme Code: ${schemeCode}`;
    addModalAmount.value = 5000;
    addModalFrequency.value = "Monthly";
    addModalStartDate.value = new Date().toISOString().slice(0, 10);
    addModal.classList.add("show");
    addModal.setAttribute("aria-hidden", "false");
  };

  const saveAddModal = () => {
    if (!addingScheme || !addModalAmount || !addModalFrequency || !addModalStartDate) {
      return;
    }

    const { schemeCode, schemeName } = addingScheme;
    const amount = parseFloat(addModalAmount.value || "0");
    const frequency = addModalFrequency.value;
    const startDate = addModalStartDate.value;

    if (amount <= 0 || !startDate) {
      addModalAmount.focus();
      return;
    }

    const items = loadCartItems().filter((item) => item.schemeCode !== schemeCode);
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
