document.addEventListener("DOMContentLoaded", function() {
  const fileListEl = document.getElementById("file-list");
  const refreshBtn = document.getElementById("refresh-btn");
  const summaryStatsEl = document.getElementById("summary-stats");
  const uploadBtn = document.getElementById("upload-btn");
  const uploadSection = document.getElementById("upload-section");
  const uploadForm = document.getElementById("upload-form");
  const cancelUploadBtn = document.getElementById("cancel-upload");

  // Fetch dashboard stats and file list from backend.
  function loadDashboard() {
    fetch("/api/dashboard_stats")
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          showToast("Error: " + data.error);
          return;
        }
        // Render summary stats.
        summaryStatsEl.innerHTML = `
          <div class="stat-blob">
            <div class="stat-number">${data.total_files}</div>
            <div class="stat-label">Total Files</div>
          </div>
          <div class="stat-blob">
            <div class="stat-number">${data.reviewed_count}</div>
            <div class="stat-label">Reviewed</div>
          </div>
          <div class="stat-blob">
            <div class="stat-number">${data.matched_count}</div>
            <div class="stat-label">Matched</div>
          </div>
          <div class="stat-blob">
            <div class="stat-number">${data.nomatch_count}</div>
            <div class="stat-label">No Match</div>
          </div>
        `;
        // Render file table.
        fileListEl.innerHTML = "";
        data.files.forEach(file => {
          const tr = document.createElement("tr");
          tr.className = "file-row";
          
          const statusClass = file.status === "completed" ? "status-complete" : 
                            file.status === "partially reviewed" ? "status-partial" : "status-never";
          
          tr.innerHTML = `
            <td>${file.name}</td>
            <td><span class="status-badge ${statusClass}">${file.status}</span></td>
            <td>${file.reviewed}/${data.total_files}</td>
            <td>🎯 Process</td>
          `;
          // Make row clickable to load the image page.
          tr.addEventListener("click", () => {
            window.location.href = `/image/${file.name}`;
          });
          fileListEl.appendChild(tr);
        });
      })
      .catch(err => {
        console.error("Error loading dashboard:", err);
        showToast("Error loading dashboard");
      });
  }

  // Refresh dashboard.
  refreshBtn.addEventListener("click", () => {
    showToast("Refreshing dashboard...");
    loadDashboard();
  });

  // Show upload form.
  uploadBtn.addEventListener("click", () => {
    uploadSection.style.display = "block";
  });

  // Cancel upload.
  cancelUploadBtn.addEventListener("click", () => {
    uploadSection.style.display = "none";
  });

  // Handle file upload.
  uploadForm.addEventListener("submit", function(e) {
    e.preventDefault();
    const formData = new FormData(uploadForm);
    fetch("/api/upload_file", {
      method: "POST",
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        showToast("Upload Error: " + data.error);
      } else {
        showToast("File uploaded successfully");
        uploadSection.style.display = "none";
        loadDashboard();
      }
    })
    .catch(err => {
      console.error("Error uploading file:", err);
      showToast("Error uploading file");
    });
  });

  // Initial load.
  loadDashboard();
});
