document.addEventListener("DOMContentLoaded", function() {
  const filename = window.location.pathname.split("/").pop();
  const signaturesListEl = document.getElementById("signatures-list");
  const signatureDetailsEl = document.getElementById("signature-details");
  const panzoomContainer = document.getElementById("panzoom-container");

  // Local cache for DB search results (transient only).
  const dbResultsCache = {};

  // Initialize Panzoom for the image container.
  const panzoomInstance = Panzoom(panzoomContainer, {
    maxScale: 5,
    minScale: 1,
    contain: 'invert'
  });
  panzoomContainer.parentElement.addEventListener('wheel', panzoomInstance.zoomWithWheel);

  // Zoom controls.
  document.getElementById("zoom-in").addEventListener("click", () => panzoomInstance.zoomIn());
  document.getElementById("zoom-out").addEventListener("click", () => panzoomInstance.zoomOut());
  document.getElementById("reset-zoom").addEventListener("click", () => panzoomInstance.reset());

  // Load all extracted signatures for this image.
  // The backend is expected to return all signature records (reviewed and unreviewed)
  fetch("/api/trigger_processing", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: filename })
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      signaturesListEl.innerHTML = `<p class="text-danger">${data.error}</p>`;
      return;
    }
    const signatures = data.signatures;
    if (!signatures || signatures.length === 0) {
      signaturesListEl.innerHTML = "<p>No signatures extracted.</p>";
      return;
    }
    // For each signature record, render a card.
    signatures.forEach((entry, index) => {
      const sig = entry.signature;
      const card = document.createElement("div");
      card.className = "signature-card status-default";
      card.innerHTML = `<strong>Signature ${index+1}</strong><br>
                        Line: ${sig.signature_line}<br>
                        Date: ${sig.date}<br>
                        Name: ${sig.first_name} ${sig.last_name}<br>
                        <div class="mt-2">
                          <button class="btn btn-sm btn-info me-1" onclick='loadSignatureDetails(${JSON.stringify(sig)})'>Load Details</button>
                          <button class="btn btn-sm btn-warning me-1" onclick='editSignature(${JSON.stringify(sig)}, this)'>Edit</button>
                          <button class="btn btn-sm btn-danger" onclick='markNoMatch(${JSON.stringify(sig)})'>No Match</button>
                        </div>`;
      card.addEventListener("click", () => {
        document.querySelectorAll(".signature-card").forEach(el => el.classList.remove("active"));
        card.classList.add("active");
      });
      signaturesListEl.appendChild(card);
    });
  })
  .catch(err => {
    console.error("Error processing image:", err);
    signaturesListEl.innerHTML = `<p class="text-danger">Error processing image.</p>`;
  });

  // Function to load detailed DB search results for a signature.
  window.loadSignatureDetails = function(sig) {
    // Use signature_line as a unique key for caching.
    if (dbResultsCache[sig.signature_line]) {
      signatureDetailsEl.innerHTML = dbResultsCache[sig.signature_line];
      return;
    }
    signatureDetailsEl.innerHTML = "<p>Loading details...</p>";
    fetch("/api/signature_details", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signature: sig })
    })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        signatureDetailsEl.innerHTML = `<p class="text-danger">${data.error}</p>`;
        return;
      }
      let html = `<h5>Voter Matches for Signature Line ${sig.signature_line}</h5>`;
      const methods = ["exact_matches", "address_matches", "fuzzy_name_matches", "fuzzy_address_matches"];
      methods.forEach(method => {
        html += `<h6>${method.replace('_', ' ').toUpperCase()}</h6>`;
        const matches = data.results[method];
        if (!matches || matches.length === 0) {
          html += `<p>No matches found.</p>`;
        } else {
          html += `<table class="table table-sm table-bordered">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Name</th>
                        <th>Address</th>
                        <th>Extra</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>`;
          matches.forEach((match, idx) => {
            html += `<tr>
                       <td>${idx+1}</td>
                       <td>${match.FirstName} ${match.LastName}</td>
                       <td>${match.RegStreetNumber} ${match.RegStreetName}</td>
                       <td>${match.PoliticalParty || ''} ${match.fuzzy_score || match.address_fuzzy_score || ''}</td>
                       <td><button class="btn btn-sm btn-primary" onclick='selectCandidate(${JSON.stringify(sig)}, ${JSON.stringify(match)})'>Select</button></td>
                     </tr>`;
          });
          html += `</tbody></table>`;
        }
      });
      dbResultsCache[sig.signature_line] = html;
      signatureDetailsEl.innerHTML = html;
    })
    .catch(err => {
      console.error("Error loading signature details:", err);
      signatureDetailsEl.innerHTML = `<p class="text-danger">Error loading details.</p>`;
    });
  };

  // Function to finalize candidate selection.
  window.selectCandidate = function(sig, candidate) {
    if (confirm("Finalize selection of this candidate?")) {
      fetch("/api/select_candidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: filename, signature: sig, candidate: candidate })
      })
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          alert("Error: " + data.error);
          return;
        }
        alert("Candidate finalized!");
        updateSignatureCardStatus(sig.signature_line, "match");
      })
      .catch(err => console.error("Error finalizing candidate:", err));
    }
  };

  // Function to allow editing of signature card values.
  window.editSignature = function(sig, btnElem) {
    const card = btnElem.closest('.signature-card');
    card.innerHTML = `
      <div class="mb-2">
        <label class="form-label">Signature Line:</label>
        <input type="text" class="form-control" id="edit-signature_line" value="${sig.signature_line}">
      </div>
      <div class="mb-2">
        <label class="form-label">Date:</label>
        <input type="text" class="form-control" id="edit-date" value="${sig.date}">
      </div>
      <div class="mb-2">
        <label class="form-label">First Name:</label>
        <input type="text" class="form-control" id="edit-first_name" value="${sig.first_name}">
      </div>
      <div class="mb-2">
        <label class="form-label">Last Name:</label>
        <input type="text" class="form-control" id="edit-last_name" value="${sig.last_name}">
      </div>
      <div class="mb-2">
        <label class="form-label">Address Number:</label>
        <input type="text" class="form-control" id="edit-address_number" value="${sig.address_number || ''}">
      </div>
      <div class="mb-2">
        <label class="form-label">Address Name:</label>
        <input type="text" class="form-control" id="edit-address_name" value="${sig.address_name || ''}">
      </div>
      <div class="mt-2">
        <button class="btn btn-sm btn-success me-1" onclick="submitEditSignature()">Re‑run Search</button>
        <button class="btn btn-sm btn-secondary" onclick="cancelEdit(this, ${JSON.stringify(sig)})">Cancel</button>
      </div>`;
  };

  window.submitEditSignature = function() {
    const card = document.querySelector(".signature-card.active") || event.target.closest('.signature-card');
    const newSig = {
      signature_line: document.getElementById("edit-signature_line").value,
      date: document.getElementById("edit-date").value,
      first_name: document.getElementById("edit-first_name").value,
      last_name: document.getElementById("edit-last_name").value,
      address_number: document.getElementById("edit-address_number").value,
      address_name: document.getElementById("edit-address_name").value
    };
    // Clear any cached result for this signature.
    delete dbResultsCache[newSig.signature_line];
    loadSignatureDetails(newSig);
    card.innerHTML = `<strong>Edited Signature</strong><br>
                      Line: ${newSig.signature_line}<br>
                      Date: ${newSig.date}<br>
                      Name: ${newSig.first_name} ${newSig.last_name}<br>
                      <div class="mt-2">
                        <button class="btn btn-sm btn-info me-1" onclick='loadSignatureDetails(${JSON.stringify(newSig)})'>Load Details</button>
                        <button class="btn btn-sm btn-warning me-1" onclick='editSignature(${JSON.stringify(newSig)}, this)'>Edit</button>
                        <button class="btn btn-sm btn-danger" onclick='markNoMatch(${JSON.stringify(newSig)})'>No Match</button>
                      </div>`;
  };

  window.cancelEdit = function(btn, originalSig) {
    const card = btn.closest('.signature-card');
    card.innerHTML = `<strong>Signature</strong><br>
                      Line: ${originalSig.signature_line}<br>
                      Date: ${originalSig.date}<br>
                      Name: ${originalSig.first_name} ${originalSig.last_name}<br>
                      <div class="mt-2">
                        <button class="btn btn-sm btn-info me-1" onclick='loadSignatureDetails(${JSON.stringify(originalSig)})'>Load Details</button>
                        <button class="btn btn-sm btn-warning me-1" onclick='editSignature(${JSON.stringify(originalSig)}, this)'>Edit</button>
                        <button class="btn btn-sm btn-danger" onclick='markNoMatch(${JSON.stringify(originalSig)})'>No Match</button>
                      </div>`;
  };

  // Mark a signature card as "No Match" (per card)
  window.markNoMatch = function(sig) {
    const cards = document.querySelectorAll(".signature-card");
    let targetCard = null;
    cards.forEach(card => {
      if (card.innerHTML.includes(sig.signature_line)) {
        targetCard = card;
      }
    });
    if (!targetCard) {
      alert("Signature card not found.");
      return;
    }
    if (confirm("Mark this signature as having no match?")) {
      targetCard.classList.remove("status-default", "status-match");
      targetCard.classList.add("status-nomatch");
      signatureDetailsEl.innerHTML = `<p class="text-danger">No match selected for signature line ${sig.signature_line}.</p>`;
    }
  };

  // Helper to update a signature card's status.
  function updateSignatureCardStatus(signatureLine, status) {
    const cards = document.querySelectorAll(".signature-card");
    cards.forEach(card => {
      if (card.innerHTML.includes(signatureLine)) {
        if (status === "match") {
          card.classList.remove("status-default", "status-nomatch");
          card.classList.add("status-match");
        } else if (status === "no match") {
          card.classList.remove("status-default", "status-match");
          card.classList.add("status-nomatch");
        } else {
          card.classList.remove("status-match", "status-nomatch");
          card.classList.add("status-default");
        }
      }
    });
  }

  // Global action: Rerun Grok inferences.
  window.rerunGrok = function() {
    if (confirm("Re-run grok inferences for this image? This will reprocess the image.")) {
      fetch("/api/trigger_processing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: filename })
      })
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          alert("Error: " + data.error);
          return;
        }
        alert("Grok inferences re-run. Refreshing signature list.");
        location.reload();
      })
      .catch(err => console.error("Error rerunning grok:", err));
    }
  };

  // Global action: Return to Dashboard.
  window.goToDashboard = function() {
    window.location.href = "/";
  };
});
