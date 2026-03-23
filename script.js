document.addEventListener("DOMContentLoaded", () => {
  
  /* ---------- TOGGLE SECTIONS ---------- */
  function toggleSection(selectId, containerId) {
    const select = document.getElementById(selectId);
    const container = document.getElementById(containerId);
    if (!select || !container) return;

    select.addEventListener("change", () => {
      if (select.value === "yes") {
        container.classList.remove("hidden");
      } else {
        container.classList.add("hidden");
        container.querySelectorAll("input").forEach(i => i.value = "");
      }
    });
  }

  // Laptop fields (show only when laptop is selected)
  const deviceType = document.getElementById("deviceType");
  const laptopFields = document.getElementById("laptopFields");
  if (deviceType && laptopFields) {
    deviceType.addEventListener("change", () => {
      if (deviceType.value === "laptop") {
        laptopFields.classList.remove("hidden");
      } else {
        laptopFields.classList.add("hidden");
        laptopFields.querySelectorAll("input").forEach(i => i.value = "");
      }
    });
  }

  // Peripherals toggles
  toggleSection("hasKeyboard", "keyboardFields");
  toggleSection("hasMouse", "mouseFields");
  toggleSection("hasHeadphone", "headphoneFields");
  toggleSection("hasWebcam", "webcamContainer");

  // Monitor toggle
  const hasMonitor = document.getElementById("hasMonitor");
  const monitorContainer = document.getElementById("monitorContainer");
  
  if (hasMonitor && monitorContainer) {
    hasMonitor.addEventListener("change", () => {
      if (hasMonitor.value === "yes") {
        monitorContainer.classList.remove("hidden");
      } else {
        monitorContainer.classList.add("hidden");
        // Reset to single monitor
        monitorContainer.innerHTML = `
          <div class="monitor">
            <input name="monitor_brand[]" placeholder="Monitor Brand">
            <input name="monitor_sn[]" placeholder="Monitor Serial Number">
            <button type="button" class="btn-remove" onclick="removeMonitor(this)">✕</button>
          </div>
          <button type="button" id="addMonitor" class="btn-add">+ Add Another Monitor</button>
        `;
      }
    });
  }
});
