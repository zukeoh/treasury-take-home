(() => {
  const form = document.querySelector("#review-form");
  if (!form) return;

  const imageInput = document.querySelector("#images");
  const fileSummary = document.querySelector("#file-summary");
  const imageList = document.querySelector("#image-list");
  const imageItemTemplate = document.querySelector("#image-item-template");
  const loadingTemplate = document.querySelector("#review-loading-template");
  const dropZone = document.querySelector("#drop-zone");
  const sourceButtons = [...document.querySelectorAll("[data-source]")];
  const applicationDataStep = document.querySelector("#application-data-step");
  const manualPanel = document.querySelector("#manual-panel");
  const manualContainer = document.querySelector("#manual-applications");
  const manualEmpty = document.querySelector("#manual-empty");
  const manualTemplate = document.querySelector("#manual-application-template");
  const manualPayload = document.querySelector("#manual_applications");
  const csvPanel = document.querySelector("#csv-panel");
  const csvInput = document.querySelector("#application_csv");
  const submitButton = document.querySelector("#verify-button");
  const maxImages = Number(imageInput.dataset.maxImages);
  const previewUrls = new Map();
  let selectedFiles = [];
  let currentSource = "manual";

  const fileKey = (file) => file.name.toLocaleLowerCase();

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const isSupportedImage = (file) => {
    const extension = file.name.split(".").pop().toLocaleLowerCase();
    return ["jpg", "jpeg", "png"].includes(extension);
  };

  const syncInputFiles = () => {
    const transfer = new DataTransfer();
    selectedFiles.forEach((file) => transfer.items.add(file));
    imageInput.files = transfer.files;
  };

  const releasePreviewUrls = () => {
    previewUrls.forEach((url) => URL.revokeObjectURL(url));
    previewUrls.clear();
  };

  const readSection = (section) => {
    const record = { file_name: section.dataset.fileName };
    section.querySelectorAll("[data-field]").forEach((control) => {
      record[control.dataset.field] = control.type === "checkbox" ? control.checked : control.value.trim();
    });
    return record;
  };

  const updateBeverageFields = (section) => {
    const selected = section.querySelector('[data-field="beverage_type"]').value;
    section.querySelectorAll("[data-beverage-section]").forEach((group) => {
      const active = group.dataset.beverageSection === selected;
      group.hidden = !active;
      group.querySelectorAll("input, select").forEach((control) => {
        control.disabled = !active;
      });
    });
  };

  const updateCountry = (section) => {
    const imported = section.querySelector('[data-field="imported"]');
    const countryWrap = section.querySelector("[data-country-wrap]");
    const countryInput = section.querySelector('[data-field="country_of_origin"]');
    const enabled = imported.checked;
    countryWrap.classList.toggle("is-disabled", !enabled);
    countryInput.disabled = !enabled;
    countryInput.required = enabled;
  };

  const assignControlIds = (section, index) => {
    section.querySelectorAll("[data-field]").forEach((control) => {
      const id = `application-${index}-${control.dataset.field}`;
      control.id = id;
      const label = section.querySelector(`[data-label-for="${control.dataset.field}"]`);
      if (label) label.htmlFor = id;
    });
    const imported = section.querySelector('[data-field="imported"]');
    const country = section.querySelector('[data-field="country_of_origin"]');
    const help = section.querySelector("[data-imported-help]");
    help.id = `application-${index}-imported-help`;
    imported.setAttribute("aria-controls", country.id);
    imported.setAttribute("aria-describedby", help.id);
  };

  const createSection = (file, index, previous) => {
    const section = manualTemplate.content.firstElementChild.cloneNode(true);
    section.dataset.fileName = file.name;
    section.querySelector("[data-file-title]").textContent = file.name;
    const thumbnail = section.querySelector("[data-application-thumbnail]");
    thumbnail.src = previewUrls.get(fileKey(file));
    thumbnail.alt = `Preview of ${file.name}`;
    assignControlIds(section, index);
    if (previous) {
      section.querySelectorAll("[data-field]").forEach((control) => {
        const value = previous[control.dataset.field];
        if (control.type === "checkbox") control.checked = Boolean(value);
        else if (value !== undefined) control.value = value;
      });
    }
    updateBeverageFields(section);
    updateCountry(section);
    return section;
  };

  const rebuildManualSections = () => {
    const previous = new Map(
      [...manualContainer.querySelectorAll(".manual-application")].map((section) => [
        section.dataset.fileName.toLocaleLowerCase(),
        readSection(section),
      ]),
    );
    const files = selectedFiles;
    const normalizedNames = files.map((file) => file.name.toLocaleLowerCase());
    const duplicateNames = new Set(normalizedNames).size !== normalizedNames.length;
    imageInput.setCustomValidity(duplicateNames ? "Each image must have a unique file name." : "");
    manualContainer.replaceChildren(
      ...files.map((file, index) => createSection(file, index + 1, previous.get(file.name.toLocaleLowerCase()))),
    );
    manualEmpty.hidden = files.length > 0;
    if (currentSource === "csv") setManualAvailability(false);
  };

  const renderImageList = () => {
    const cards = selectedFiles.map((file) => {
      const key = fileKey(file);
      if (!previewUrls.has(key)) previewUrls.set(key, URL.createObjectURL(file));
      const card = imageItemTemplate.content.firstElementChild.cloneNode(true);
      const thumbnail = card.querySelector("[data-image-thumbnail]");
      const removeButton = card.querySelector("[data-remove-file]");
      card.dataset.fileKey = key;
      thumbnail.src = previewUrls.get(key);
      thumbnail.alt = `Preview of ${file.name}`;
      card.querySelector("[data-image-name]").textContent = file.name;
      card.querySelector("[data-image-size]").textContent = formatFileSize(file.size);
      removeButton.dataset.fileKey = key;
      removeButton.setAttribute("aria-label", `Remove ${file.name}`);
      return card;
    });
    imageList.replaceChildren(...cards);
  };

  const highlightDuplicates = (duplicateKeys) => {
    duplicateKeys.forEach((key) => {
      const card = [...imageList.children].find((item) => item.dataset.fileKey === key);
      if (!card) return;
      card.classList.remove("is-duplicate");
      void card.offsetWidth;
      card.classList.add("is-duplicate");
      window.setTimeout(() => card.classList.remove("is-duplicate"), 1000);
    });
  };

  const refreshSelectedFiles = (message = "") => {
    if (!selectedFiles.length) {
      fileSummary.textContent = "No images selected";
      dropZone.classList.remove("has-files");
    } else {
      const totalMb = selectedFiles.reduce((sum, file) => sum + file.size, 0) / 1024 / 1024;
      fileSummary.textContent = `${selectedFiles.length} image${selectedFiles.length === 1 ? "" : "s"} selected · ${totalMb.toFixed(1)} MB total${message}`;
      dropZone.classList.add("has-files");
    }
    renderImageList();
    rebuildManualSections();
    const applicationLocked = selectedFiles.length === 0;
    applicationDataStep.classList.toggle("is-locked", applicationLocked);
    applicationDataStep.inert = applicationLocked;
    applicationDataStep.setAttribute("aria-disabled", String(applicationLocked));
  };

  const addFiles = (files) => {
    const knownNames = new Set(selectedFiles.map(fileKey));
    const duplicateKeys = new Set();
    let unsupportedCount = 0;
    let limitCount = 0;
    let addedCount = 0;
    files.forEach((file) => {
      const key = fileKey(file);
      if (!isSupportedImage(file)) {
        unsupportedCount += 1;
      } else if (knownNames.has(key)) {
        duplicateKeys.add(key);
      } else if (selectedFiles.length >= maxImages) {
        limitCount += 1;
      } else {
        selectedFiles.push(file);
        knownNames.add(key);
        addedCount += 1;
      }
    });
    syncInputFiles();
    const notes = [];
    if (unsupportedCount) notes.push(`${unsupportedCount} unsupported file skipped`);
    if (limitCount) notes.push(`${limitCount} over the ${maxImages}-image limit skipped`);
    if (addedCount || unsupportedCount || limitCount || !files.length) {
      refreshSelectedFiles(notes.length ? ` · ${notes.join(" · ")}` : "");
    }
    highlightDuplicates(duplicateKeys);
  };

  const setManualAvailability = (enabled) => {
    manualPayload.disabled = !enabled;
    manualContainer.querySelectorAll(".manual-application").forEach((section) => {
      section.querySelectorAll("[data-field]").forEach((control) => {
        control.disabled = !enabled;
      });
      if (enabled) {
        updateBeverageFields(section);
        updateCountry(section);
      }
    });
  };

  const selectSource = (source) => {
    currentSource = source;
    const useCsv = source === "csv";
    sourceButtons.forEach((button) => {
      const active = button.dataset.source === source;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    csvPanel.hidden = !useCsv;
    manualPanel.hidden = useCsv;
    csvInput.required = useCsv;
    csvInput.disabled = !useCsv;
    setManualAvailability(!useCsv);
  };

  const focusNextManualControl = (current) => {
    const controls = [
      ...manualContainer.querySelectorAll(
        'input:not([disabled]):not([type="hidden"]), select:not([disabled])',
      ),
    ];
    const index = controls.indexOf(current);
    if (index >= 0 && index + 1 < controls.length) controls[index + 1].focus();
    else submitButton.focus();
  };

  sourceButtons.forEach((button) => {
    button.addEventListener("click", () => selectSource(button.dataset.source));
  });

  manualContainer.addEventListener("change", (event) => {
    const control = event.target.closest("[data-field]");
    const section = event.target.closest(".manual-application");
    if (!control || !section) return;
    if (control.dataset.field === "beverage_type") updateBeverageFields(section);
    if (control.dataset.field === "imported") updateCountry(section);
  });

  manualContainer.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    const control = event.target.closest("[data-field]");
    const section = event.target.closest(".manual-application");
    if (!control || !section) return;
    event.preventDefault();
    if (control.type === "checkbox") {
      control.checked = !control.checked;
      updateCountry(section);
      if (control.checked) {
        section.querySelector('[data-field="country_of_origin"]').focus();
        return;
      }
    }
    focusNextManualControl(control);
  });

  imageInput.addEventListener("change", () => addFiles([...imageInput.files]));
  imageList.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-file]");
    if (!removeButton) return;
    const index = selectedFiles.findIndex((file) => fileKey(file) === removeButton.dataset.fileKey);
    if (index < 0) return;
    const [removed] = selectedFiles.splice(index, 1);
    const key = fileKey(removed);
    URL.revokeObjectURL(previewUrls.get(key));
    previewUrls.delete(key);
    syncInputFiles();
    refreshSelectedFiles();
    const remainingButtons = imageList.querySelectorAll("[data-remove-file]");
    if (remainingButtons.length) remainingButtons[Math.min(index, remainingButtons.length - 1)].focus();
    else dropZone.focus();
  });

  dropZone.addEventListener("keydown", (event) => {
    if (!["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    imageInput.click();
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.add("is-dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, () => dropZone.classList.remove("is-dragging"));
  });
  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    if (event.dataTransfer.files.length) addFiles([...event.dataTransfer.files]);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!manualPanel.hidden) {
      manualPayload.value = JSON.stringify(
        [...manualContainer.querySelectorAll(".manual-application")].map(readSection),
      );
    }
    const submission = new FormData(form);
    const labelCount = selectedFiles.length;
    submitButton.disabled = true;
    submitButton.querySelector("span").textContent = "Reading Labels…";
    submitButton.classList.add("is-loading");
    const loadingView = loadingTemplate.content.cloneNode(true);
    loadingView.querySelector("[data-loading-count]").textContent =
      `${labelCount} label${labelCount === 1 ? "" : "s"} queued for verification.`;
    const estimatedSeconds = Math.max(4, Math.ceil(labelCount * 3.5));
    const estimateText = loadingView.querySelector("[data-loading-estimate]");
    const elapsedText = loadingView.querySelector("[data-loading-elapsed]");
    const progressFill = loadingView.querySelector("[data-progress-fill]");
    estimateText.textContent = `Estimated time: about ${estimatedSeconds} seconds, based on 3.5 seconds per image.`;
    document.title = "Review results · Alcohol Label Pre-Screener";
    const processingGuardState = { navigationGuard: "processing" };
    let allowProcessingNavigation = false;
    const confirmProcessingNavigation = () => window.confirm(
      "Label verification is still processing. Leave this page and stop waiting for results?",
    );
    const guardProcessingLink = (clickEvent) => {
      const link = clickEvent.target.closest?.("a[href]");
      if (!link || link.target === "_blank" || link.hasAttribute("download")) return;
      if (allowProcessingNavigation || confirmProcessingNavigation()) {
        allowProcessingNavigation = true;
      } else {
        clickEvent.preventDefault();
      }
    };
    const guardProcessingHistory = () => {
      if (allowProcessingNavigation || confirmProcessingNavigation()) {
        allowProcessingNavigation = true;
        window.history.back();
      } else {
        window.history.pushState(processingGuardState, "", "/verify");
      }
    };
    const guardProcessingUnload = (unloadEvent) => {
      if (allowProcessingNavigation) return;
      unloadEvent.preventDefault();
      unloadEvent.returnValue = "";
    };
    const removeProcessingGuards = () => {
      document.removeEventListener("click", guardProcessingLink);
      window.removeEventListener("popstate", guardProcessingHistory);
      window.removeEventListener("beforeunload", guardProcessingUnload);
    };
    window.history.pushState({ navigationBase: "processing" }, "", "/verify");
    window.history.pushState(processingGuardState, "", "/verify");
    document.addEventListener("click", guardProcessingLink);
    window.addEventListener("popstate", guardProcessingHistory);
    window.addEventListener("beforeunload", guardProcessingUnload);
    document.querySelector("main").replaceChildren(loadingView);
    window.scrollTo({ top: 0, behavior: "auto" });
    const loadingStarted = Date.now();
    const updateEstimatedProgress = () => {
      const elapsedSeconds = Math.floor((Date.now() - loadingStarted) / 1000);
      const percent = Math.min(95, (elapsedSeconds / estimatedSeconds) * 100);
      progressFill.style.width = `${percent}%`;
      elapsedText.textContent = elapsedSeconds > estimatedSeconds
        ? `Elapsed time: ${elapsedSeconds} seconds. This review is taking longer than the general estimate.`
        : `Elapsed time: ${elapsedSeconds} second${elapsedSeconds === 1 ? "" : "s"}.`;
    };
    updateEstimatedProgress();
    const progressTimer = window.setInterval(updateEstimatedProgress, 500);

    try {
      const response = await fetch("/verify", { method: "POST", body: submission });
      const html = await response.text();
      window.clearInterval(progressTimer);
      removeProcessingGuards();
      if (response.ok) window.history.replaceState({ navigationGuard: "results" }, "", "/verify");
      else window.history.replaceState({}, "", "/");
      releasePreviewUrls();
      document.open();
      document.write(html);
      document.close();
    } catch (error) {
      window.clearInterval(progressTimer);
      removeProcessingGuards();
      if (allowProcessingNavigation) return;
      window.history.replaceState({}, "", "/");
      const card = document.querySelector(".processing-card");
      card.classList.add("processing-error");
      card.querySelector("h2").textContent = "Verification Could Not Be Completed";
      card.querySelector("p").textContent = "Check that the local service is running, then start the review again.";
      card.querySelector(".processing-track").remove();
      const retry = document.createElement("a");
      retry.className = "btn btn-primary";
      retry.href = "/";
      retry.textContent = "Return to Label Review";
      card.append(retry);
    }
  });

  selectSource("manual");
  addFiles([...imageInput.files]);
  window.addEventListener("beforeunload", releasePreviewUrls);
  const error = document.querySelector("#form-error");
  if (error) error.focus();
})();
