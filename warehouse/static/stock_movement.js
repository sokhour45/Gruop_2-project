(() => {
  "use strict";

  const form = document.querySelector("[data-stock-movement]");
  if (!form) return;

  const movementType = form.dataset.stockMovement;
  const productSelect = form.querySelector("#movement-product");
  const quantityInput = form.querySelector("#movement-quantity");
  const snapshot = form.querySelector("#movement-product-snapshot");
  const currentQuantity = form.querySelector("#movement-current-quantity");
  const unitLabel = form.querySelector("#movement-unit");
  const projectedQuantity = form.querySelector("#movement-projected-quantity");
  const projectedUnit = form.querySelector("#movement-projected-unit");
  const reorderPoint = form.querySelector("#movement-reorder-point");
  const reorderUnit = form.querySelector("#movement-reorder-unit");
  const productName = form.querySelector("#movement-product-name");
  const productLocation = form.querySelector("#movement-product-location");
  const guidance = form.querySelector("#movement-guidance");
  const useAvailableButton = form.querySelector("[data-use-available]");

  function updateSnapshot() {
    const option = productSelect.selectedOptions[0];
    const hasProduct = Boolean(option && option.value);
    snapshot.hidden = !hasProduct;
    quantityInput.setCustomValidity("");

    if (!hasProduct) {
      quantityInput.removeAttribute("max");
      if (useAvailableButton) useAvailableButton.disabled = true;
      return;
    }

    const available = Number(option.dataset.quantity);
    const reorder = Number(option.dataset.reorder);
    const quantity = Number(quantityInput.value) || 0;
    const result = movementType === "IN" ? available + quantity : available - quantity;
    const unit = option.dataset.unit || "";
    guidance.classList.remove("movement-guidance-error", "movement-guidance-warning");

    productName.textContent = option.textContent.trim().split(" (")[0];
    productLocation.textContent = option.dataset.location
      ? `Bin ${option.dataset.location}`
      : "Bin not assigned";
    currentQuantity.textContent = available.toLocaleString();
    unitLabel.textContent = unit;
    projectedQuantity.textContent = result.toLocaleString();
    projectedUnit.textContent = unit;
    reorderPoint.textContent = reorder.toLocaleString();
    reorderUnit.textContent = unit;

    if (movementType === "OUT") {
      quantityInput.max = String(available);
      if (useAvailableButton) useAvailableButton.disabled = available <= 0;
      if (quantity > available) {
        quantityInput.setCustomValidity(`Only ${available} ${unit} available.`);
        guidance.textContent = `Quantity exceeds available stock by ${quantity - available} ${unit}.`;
        guidance.classList.add("movement-guidance-error");
        return;
      }
    } else {
      quantityInput.removeAttribute("max");
    }

    guidance.classList.remove("movement-guidance-error");
    if (quantity > 0 && result <= reorder) {
      guidance.textContent = `After posting, stock will still be at or below the reorder point (${reorder} ${unit}).`;
      guidance.classList.add("movement-guidance-warning");
    } else if (quantity > 0) {
      guidance.textContent = "The projected balance is above the reorder point.";
      guidance.classList.remove("movement-guidance-warning");
    } else {
      guidance.textContent = movementType === "IN"
        ? "Enter the received quantity to preview the new balance."
        : "Enter the issue quantity to preview the remaining balance.";
      guidance.classList.remove("movement-guidance-warning");
    }
  }

  productSelect.addEventListener("change", updateSnapshot);
  quantityInput.addEventListener("input", updateSnapshot);

  form.querySelectorAll("[data-set-quantity]").forEach((button) => {
    button.addEventListener("click", () => {
      quantityInput.value = button.dataset.setQuantity;
      quantityInput.dispatchEvent(new Event("input", { bubbles: true }));
      quantityInput.focus();
    });
  });

  if (useAvailableButton) {
    useAvailableButton.addEventListener("click", () => {
      const option = productSelect.selectedOptions[0];
      if (!option || !option.value) return;
      quantityInput.value = option.dataset.quantity;
      quantityInput.dispatchEvent(new Event("input", { bubbles: true }));
      quantityInput.focus();
    });
  }

  form.addEventListener("submit", (event) => {
    updateSnapshot();
    if (!form.reportValidity()) event.preventDefault();
  });

  updateSnapshot();
})();
