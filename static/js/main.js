document.addEventListener("DOMContentLoaded", function() {
  const fileListEl = document.getElementById("file-list");
  const refreshBtn = document.getElementById("refresh-btn");
  const toastEl = document.getElementById("toast-notif");
  const toastBody = document.getElementById("toast-body");
  const toast = new bootstrap.Toast(toastEl);

  // Function to display a toast message
  function showToast(message, bgClass = 'text-bg-primary') {
    toastEl.classList.remove('text-bg-primary', 'text-bg-danger', 'text-bg-success');
    toastEl.classList.add(bgClass);
    toastBody.textContent = message;
    toast.show();
  }

  // Function to fetch file list from backend and update UI
  function loadFileList() {
    fetch("/api/files")
      .then(response => response.json())
      .then(data => {
        fileListEl.innerHTML = ""; // Clear list
        data.files.forEach(file => {
          const li = document.createElement("li");
          li.className = "list-group-item d-flex justify-content-between align-items-center";
          li.textContent = file.name;

          // Create status badge
          const badge = document.createElement("span");
          badge.className = "badge bg-secondary";
          badge.textContent = file.status;
          li.appendChild(badge);

          // For files not marked as "completed", add a Process button.
          if (file.status !== "completed") {
            const btn = document.createElement("button");
            btn.className = "btn btn-sm btn-primary ms-2";
            btn.textContent = "Process File";
            btn.addEventListener("click", (e) => {
              e.stopPropagation();
              triggerProcessing(file.name);
            });
            li.appendChild(btn);
          } else {
            // If complete, make the item clickable.
            li.classList.add("cursor-pointer");
            li.addEventListener("click", () => {
              window.location.href = `/image/${file.name}`;
            });
          }
          fileListEl.appendChild(li);
        });
      })
      .catch(err => {
        console.error("Error fetching file list:", err);
        showToast("Error fetching file list", "text-bg-danger");
      });
  }

  // Trigger file processing and auto-refresh list on completion.
  function triggerProcessing(filename) {
    fetch("/api/trigger_processing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: filename })
    })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        showToast(`Error: ${data.error}`, "text-bg-danger");
      } else {
        showToast("Processing complete. Refreshing list...", "text-bg-success");
        // Refresh the file list after a short delay to allow backend to update status.
        setTimeout(loadFileList, 1500);
      }
    })
    .catch(err => {
      console.error("Error triggering processing:", err);
      showToast("Error triggering processing", "text-bg-danger");
    });
  }

  // Manual refresh button handler
  refreshBtn.addEventListener("click", () => {
    showToast("Refreshing file list...", "text-bg-primary");
    loadFileList();
  });

  // Initial load
  loadFileList();
});
