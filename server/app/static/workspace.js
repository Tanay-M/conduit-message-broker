/* Reporting workspace enhancements. Forms and navigation remain server-rendered. */
(() => {
  const setNavigation = (open) => {
    document.body.classList.toggle("nav-open", open);
    document
      .querySelector(".mobile-nav")
      ?.setAttribute("aria-expanded", String(open));
  };
  const toast = (message, error = false) => {
    const node = document.getElementById("workspace-toast");
    if (!node) return;
    node.textContent = message;
    node.classList.toggle("error", error);
    node.hidden = false;
    clearTimeout(node.dismissTimer);
    node.dismissTimer = setTimeout(() => {
      node.hidden = true;
    }, 4500);
  };

  document.addEventListener("click", async (event) => {
    const nav = event.target.closest("[data-nav-toggle]");
    if (nav) setNavigation(!document.body.classList.contains("nav-open"));
    if (event.target.closest("[data-refresh]")) window.location.reload();
    const copy = event.target.closest("[data-copy-target]");
    if (copy) {
      try {
        await navigator.clipboard.writeText(
          document.getElementById(copy.dataset.copyTarget).textContent.trim(),
        );
        toast("SQL copied to clipboard.");
      } catch (_) {
        toast(
          "Clipboard access is unavailable. Select and copy the query.",
          true,
        );
      }
    }
    const retry = event.target.closest("[data-retry]");
    if (retry) {
      retry.disabled = true;
      retry.textContent = "Retrying…";
      try {
        const response = await fetch(
          `/api/reports/requests/${retry.dataset.retry}/retry`,
          { method: "POST" },
        );
        const body = await response.json();
        if (!response.ok)
          throw new Error(body.message || body.detail || "Retry failed.");
        window.location.reload();
      } catch (error) {
        toast(error.message, true);
        retry.disabled = false;
        retry.textContent = "Retry";
      }
    }
    const preset = event.target.closest("[data-sql-preset]");
    if (preset) {
      document.getElementById("sql-editor").value = preset.dataset.sqlPreset;
      document.getElementById("sql-editor").focus();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setNavigation(false);
    if (
      (event.ctrlKey || event.metaKey) &&
      event.key === "Enter" &&
      document.activeElement.id === "sql-editor"
    ) {
      event.preventDefault();
      document.getElementById("sql-editor").form.requestSubmit();
    }
  });

  document.addEventListener("htmx:responseError", (event) => {
    if (event.detail.target?.id !== "sql-results") return;
    let message =
      "The query could not be completed. Check the SQL and try again.";
    try {
      const body = JSON.parse(event.detail.xhr.responseText);
      const detail = body.detail || body.message;
      if (typeof detail === "string") message = detail;
    } catch (_) {
      /* Keep a readable fallback for non-JSON server responses. */
    }
    const error = document.createElement("div");
    error.className = "form-error";
    error.setAttribute("role", "alert");
    error.textContent = message;
    event.detail.target.replaceChildren(error);
  });

  document.addEventListener("DOMContentLoaded", () => {
    const refresh = document.querySelector("[data-auto-refresh]");
    if (refresh)
      setInterval(() => {
        if (
          !document.hidden &&
          !document.querySelector("button[data-retry]:disabled")
        )
          window.location.reload();
      }, Number(refresh.dataset.autoRefresh));

    const form = document.getElementById("new-report-form");
    if (!form) return;
    const config = JSON.parse(
      document.getElementById("report-catalog").textContent,
    );
    const type = document.getElementById("report-template");
    const customerSection = document.getElementById("customer-section");
    const customerField = document.getElementById("customer-field");
    const search = document.getElementById("customer-search");
    const customerId = document.getElementById("customer-id");
    const choices = document.getElementById("customer-options");
    const top = document.getElementById("top-n");

    function updateForm() {
      const template = config.catalog.find((row) => row.code === type.value);
      const statement = type.value === "customer_statement";
      const single = form.elements.scope.value === "single";
      customerSection.hidden = !statement;
      customerField.hidden = !single;
      search.required = statement && single;
      top.disabled = type.value !== "product_sales";
      document.getElementById("ranking-section").hidden = top.disabled;
      document.getElementById("template-description").textContent =
        config.descriptions[type.value];
      document.getElementById("template-sql").textContent =
        template.sql_text.trim();
      document.getElementById("query-file").textContent = `${type.value}.sql`;
    }
    type.addEventListener("change", updateForm);
    form
      .querySelectorAll("[name=scope]")
      .forEach((control) => control.addEventListener("change", updateForm));
    updateForm();

    let controller;
    let timer;
    const closeChoices = () => {
      choices.hidden = true;
      search.setAttribute("aria-expanded", "false");
    };
    async function loadCustomers() {
      controller?.abort();
      controller = new AbortController();
      try {
        const response = await fetch(
          `/web/report-customers?q=${encodeURIComponent(search.value)}`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error("Customer search is unavailable.");
        const rows = await response.json();
        choices.replaceChildren();
        for (const row of rows) {
          const option = document.createElement("button");
          option.type = "button";
          option.className = "customer-option";
          option.setAttribute("role", "option");
          option.setAttribute("aria-selected", "false");
          const name = document.createElement("span");
          name.textContent = row.full_name;
          const reference = document.createElement("small");
          reference.textContent = row.customer_ref;
          option.append(name, reference);
          option.addEventListener("click", () => {
            search.value = `${row.full_name} · ${row.customer_ref}`;
            customerId.value = row.customer_id;
            search.setCustomValidity("");
            closeChoices();
            search.focus();
          });
          choices.append(option);
        }
        if (!rows.length) {
          const empty = document.createElement("div");
          empty.className = "customer-empty";
          empty.textContent = "No matching customers. Try a name or reference.";
          choices.append(empty);
        }
        choices.hidden = false;
        search.setAttribute("aria-expanded", "true");
      } catch (error) {
        if (error.name !== "AbortError") toast(error.message, true);
      }
    }
    search.addEventListener("input", () => {
      customerId.value = "";
      search.setCustomValidity("");
      clearTimeout(timer);
      timer = setTimeout(loadCustomers, 180);
    });
    search.addEventListener("focus", () => {
      if (!customerId.value) loadCustomers();
    });
    search.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" && !choices.hidden) {
        event.preventDefault();
        choices.querySelector("button")?.focus();
      }
      if (event.key === "Escape") closeChoices();
    });
    choices.addEventListener("keydown", (event) => {
      const options = [...choices.querySelectorAll("button")];
      const index = options.indexOf(document.activeElement);
      if (event.key === "ArrowDown") {
        event.preventDefault();
        options[Math.min(index + 1, options.length - 1)]?.focus();
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        if (index <= 0) search.focus();
        else options[index - 1].focus();
      }
      if (event.key === "Escape") {
        closeChoices();
        search.focus();
      }
    });
    document.addEventListener("click", (event) => {
      if (!customerField.contains(event.target)) closeChoices();
    });
    form.addEventListener("submit", (event) => {
      if (
        type.value === "customer_statement" &&
        form.elements.scope.value === "single" &&
        !customerId.value
      ) {
        event.preventDefault();
        search.setCustomValidity("Select a customer from the search results.");
        search.reportValidity();
        return;
      }
      const submit = form.querySelector("button[type=submit]");
      submit.disabled = true;
      submit.textContent = "Submitting…";
    });
    const submitLabel = form.querySelector("button[type=submit]").innerHTML;
    window.addEventListener("pageshow", () => {
      const submit = form.querySelector("button[type=submit]");
      submit.disabled = false;
      submit.innerHTML = submitLabel;
    });
  });
})();
