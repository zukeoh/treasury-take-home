(() => {
  const filterButtons = [...document.querySelectorAll("[data-result-filter]")];
  const resultCards = [...document.querySelectorAll("[data-result-status]")];
  const filterStatus = document.querySelector("#filter-status");
  const exportButton = document.querySelector("#export-results");
  const toggleAllButton = document.querySelector("#toggle-all-results");
  const scrollTopButton = document.querySelector("#scroll-to-top");
  const imageViewer = document.querySelector("#image-viewer");
  const viewerImage = document.querySelector("#image-viewer-image");
  const viewerTitle = document.querySelector("#image-viewer-title");
  const viewerClose = document.querySelector("#image-viewer-close");
  const exportData = JSON.parse(document.querySelector("#export-data").textContent);
  let hasExported = false;
  let allowNavigation = false;
  let activeFilter = "all";
  const resultsGuardState = { navigationGuard: "results" };

  if (window.history.state?.navigationGuard !== "results") {
    window.history.replaceState({ navigationBase: "results" }, "", window.location.href);
    window.history.pushState(resultsGuardState, "", window.location.href);
  }

  const confirmUnexportedNavigation = () => window.confirm(
    "These results have not been exported. Leave this page anyway?",
  );

  document.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[href]");
    if (!link || link.target === "_blank" || link.hasAttribute("download")) return;
    if (hasExported || allowNavigation) {
      allowNavigation = true;
      return;
    }
    if (confirmUnexportedNavigation()) allowNavigation = true;
    else event.preventDefault();
  });

  window.addEventListener("popstate", () => {
    if (hasExported || allowNavigation || confirmUnexportedNavigation()) {
      allowNavigation = true;
      window.history.back();
    } else {
      window.history.pushState(resultsGuardState, "", window.location.href);
    }
  });

  window.addEventListener("beforeunload", (event) => {
    if (hasExported || allowNavigation) return;
    event.preventDefault();
    event.returnValue = "";
  });

  const applyFilter = (filter) => {
    activeFilter = filter;
    const visibleCards = [];
    resultCards.forEach((card) => {
      const visible = filter === "all"
        || (filter === "overwritten" && card.dataset.overwritten === "true")
        || card.dataset.resultStatus === filter;
      card.hidden = !visible;
      if (visible) visibleCards.push(card);
    });
    visibleCards.forEach((card, index) => {
      card.querySelector("[data-result-position]").textContent =
        `Result ${index + 1} Of ${visibleCards.length}`;
    });
    filterButtons.forEach((button) => {
      const active = button.dataset.resultFilter === filter;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const label = filter === "all" ? "all" : filter.toLocaleLowerCase();
    const visibleCount = visibleCards.length;
    filterStatus.textContent = `Showing ${visibleCount} ${label} result${visibleCount === 1 ? "" : "s"}.`;
  };

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => applyFilter(button.dataset.resultFilter));
  });

  const statusClass = (status) => status.toLocaleLowerCase().replaceAll(" ", "-");
  const statusIcon = (status) => ({ PASS: "✓", FAIL: "×", "NEEDS REVIEW": "!" })[status];

  const updateFilterCounts = () => {
    document.querySelectorAll("[data-count-status]").forEach((count) => {
      count.textContent = resultCards.filter(
        (card) => card.dataset.resultStatus === count.dataset.countStatus,
      ).length;
    });
    document.querySelector("[data-count-overwritten]").textContent = resultCards.filter(
      (card) => card.dataset.overwritten === "true",
    ).length;
  };

  const updateOverallResult = (card, finalStatus) => {
    const previousStatus = card.dataset.resultStatus;
    if (previousStatus === finalStatus) return;

    const originalStatus = card.dataset.originalStatus;
    const overwritten = finalStatus !== originalStatus;
    card.classList.remove(`result-${statusClass(previousStatus)}`);
    card.classList.add(`result-${statusClass(finalStatus)}`);
    card.dataset.resultStatus = finalStatus;
    card.dataset.overwritten = String(overwritten);
    card.querySelector("[data-status-icon]").textContent = statusIcon(finalStatus);

    card.querySelectorAll("[data-override-status]").forEach((button) => {
      const active = button.dataset.overrideStatus === finalStatus;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });

    const note = card.querySelector("[data-override-note]");
    note.hidden = !overwritten;
    note.textContent = overwritten
      ? `Overwritten: ${originalStatus} -> ${finalStatus}`
      : "";

    const row = exportData.rows.find((item) => item.file_name === card.dataset.fileName);
    if (row) {
      row.final_result = finalStatus;
      row.overwritten = finalStatus !== originalStatus;
    }

    hasExported = false;
    exportButton.textContent = "Export Results";
    updateFilterCounts();
    applyFilter(activeFilter);
  };

  resultCards.forEach((card) => {
    card.querySelectorAll("[data-override-status]").forEach((button) => {
      button.addEventListener("click", () => {
        updateOverallResult(card, button.dataset.overrideStatus);
      });
    });
  });

  const setDetailsExpanded = (card, expanded) => {
    const details = card.querySelector("[data-result-details]");
    const button = card.querySelector("[data-result-toggle]");
    details.hidden = !expanded;
    button.setAttribute("aria-expanded", String(expanded));
    button.textContent = expanded ? "Collapse Details" : "Expand Details";
  };

  const updateToggleAllLabel = () => {
    const anyExpanded = resultCards.some(
      (card) => card.querySelector("[data-result-toggle]").getAttribute("aria-expanded") === "true",
    );
    toggleAllButton.textContent = anyExpanded ? "Collapse All Details" : "Expand All Details";
  };

  resultCards.forEach((card) => {
    card.querySelector("[data-result-toggle]").addEventListener("click", () => {
      const button = card.querySelector("[data-result-toggle]");
      setDetailsExpanded(card, button.getAttribute("aria-expanded") !== "true");
      updateToggleAllLabel();
    });
  });

  toggleAllButton.addEventListener("click", () => {
    const anyExpanded = resultCards.some(
      (card) => card.querySelector("[data-result-toggle]").getAttribute("aria-expanded") === "true",
    );
    resultCards.forEach((card) => setDetailsExpanded(card, !anyExpanded));
    updateToggleAllLabel();
  });

  scrollTopButton.addEventListener("click", () => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
  });

  document.querySelectorAll("[data-image-open]").forEach((button) => {
    button.addEventListener("click", () => {
      const thumbnail = button.querySelector("img");
      const fileName = thumbnail.alt.replace(/^Preview of /, "");
      viewerImage.src = thumbnail.src;
      viewerImage.alt = `Large preview of ${fileName}`;
      viewerTitle.textContent = fileName;
      imageViewer.showModal();
    });
  });

  viewerClose.addEventListener("click", () => imageViewer.close());
  imageViewer.addEventListener("click", (event) => {
    if (event.target === imageViewer) imageViewer.close();
  });
  imageViewer.addEventListener("close", () => {
    viewerImage.removeAttribute("src");
    viewerImage.alt = "";
  });

  const csvCell = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;

  exportButton.addEventListener("click", () => {
    const lines = [
      exportData.columns.map(csvCell).join(","),
      ...exportData.rows.map((row) => exportData.columns.map((column) => csvCell(row[column])).join(",")),
    ];
    const blob = new Blob(["\ufeff", lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "ttb-label-review-results.csv";
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
    hasExported = true;
    exportButton.textContent = "Results Exported ✓";
  });

})();
