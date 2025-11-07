const port = window.location.port ? `:${window.location.port}` : "";
const wsProtocol = location.protocol === "https:" ? "wss" : "ws";
const wsUrl = `${wsProtocol}://${window.location.hostname}${port}/ws/`;

let ws = new WebSocket(wsUrl);
setup_ws_events();

setInterval(ping, 1000 * 15);
ping();
function ping() {
  if (ws.readyState == WebSocket.OPEN) {
    ws.send(
      JSON.stringify({ function: "ping", location: window.location.pathname })
    );
  } else {
    setTimeout(() => {
      // If the connection is closed, try to reconnect, but double check if it's still closed
      if (ws.readyState != WebSocket.OPEN) {
        ws = new WebSocket(wsUrl);
        setup_ws_events();
      }
    }, 10000);
  }
}

function setup_ws_events() {
  ws.onopen = () => {
    console.log("Connected to WebSocket");
    document.dispatchEvent(new CustomEvent('ws-connected'));
    ping();
  };

  ws.onmessage = (event) => {
    let data = JSON.parse(event.data);

    if ("request_id" in data) {
      let resolve = requestMap.get(data.request_id);
      resolve(data);
      requestMap.delete(data.request_id);
      if (requestMap.size == 0) {
        hideLoading();
      }
      return;
    }
    if ("call_function" in data){
      window[data["call_function"]](data);
      if (data.call_function === "promptUpdate") {
        if (window.onPromptUpdate) {
          window.onPromptUpdate(data);
        }
      }
    }
    // Forward broadcast events to jad.transport so panes can react live
    if (data && data.event) {
      try {
        if (window.jad && window.jad.transport && typeof window.jad.transport.publish === 'function') {
          window.jad.transport.publish({ ts: Date.now(), transport: 'ws', direction: 'in', endpoint: 'broadcast', event: data.event, payload: data });
        }
      } catch (_) { }
    }
  };

  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
  };

  ws.onclose = () => {
    console.log("Disconnected from WebSocket");
    document.dispatchEvent(new CustomEvent('ws-disconnected'));
  };
}
const requestMap = new Map();

function handle_auto_mail_toggle_live_update(updateData) {
  const autoMailEnabled = updateData.auto_mail_enabled;
  const message = updateData.message;

  // Find all auto mail toggle checkboxes on the page
  const autoMailToggles = document.querySelectorAll('input[data-function*="toggleAutoMail"]');

  autoMailToggles.forEach(toggle => {
    // Only update if the current state is different from the new state
    if (toggle.checked !== autoMailEnabled) {
      toggle.checked = autoMailEnabled;
    }
  });

  // Show a subtle notification that the state was updated by another user
  send_toast(
    `${message} (door andere gebruiker)`,
    "info",
    "Live update",
    3000
  );

  // Update any disabled states based on auto_mail status
  updateMailerFormStates(autoMailEnabled);
}

function updateMailerFormStates(autoMailEnabled) {
  // Find elements that should be disabled when auto_mail is enabled
  const elementsToDisable = document.querySelectorAll('[data-function*="showWarningAutoMail"]');

  elementsToDisable.forEach(element => {
    if (autoMailEnabled) {
      element.classList.add('switch-disabled');
      element.setAttribute('data-function', 'click->showWarningAutoMail');
    } else {
      element.classList.remove('switch-disabled');
      // Restore original data-endpoint if it exists
      const originalEndpoint = element.getAttribute('data-original-endpoint');
      if (originalEndpoint) {
        element.setAttribute('data-endpoint', originalEndpoint);
        element.removeAttribute('data-function');
      }
    }
  });
}

function process_mutations(mutations) {
  for (const mutation of mutations) {
    if (mutation.type == "attributes") {
      let attr = mutation.target.getAttributeNode(mutation.attributeName);
      if (attr && ["data-endpoint", "data-function"].includes(attr.name)) {
        handle_attribute(mutation.target, attr);
      }
    } else if (mutation.type == "childList") {
      for (const node of Array.from(mutation.addedNodes)) {
        if (node.nodeType == Node.ELEMENT_NODE) {
          if (
            node.hasAttribute("data-endpoint") ||
            node.hasAttribute("data-function")
          ) {
            handle_attribute(
              node,
              node.getAttributeNode("data-endpoint") ||
              node.getAttributeNode("data-function")
            );
          }
          for (const element of Array.from(
            node.querySelectorAll("[data-endpoint], [data-function]")
          )) {
            handle_attribute(
              element,
              element.getAttributeNode("data-endpoint") ||
              element.getAttributeNode("data-function")
            );
          }
        }
      }
    }
  }
}

function handle_attribute(element, attr) {
  let attr_values = attr.value.trim().split(" ");
  for (let value of attr_values) {
    // Split into eventName and endpoint if value contains ->
    if (attr.name == "data-endpoint") {
      let [eventName, endpoint] = value.split("->");
      element.addEventListener(eventName, (event) =>
        ws_request(event, endpoint)
      );
    } else if (attr.name == "data-function") {
      let [eventName, funcName] = value.split("->");
      element.addEventListener(eventName, (event) => window[funcName](event));
    }
  }
}

function storePendingToast(body, status = "default", title = "", delete_time = 2000) {
  const toastData = {
    title: title,
    message: body,
    status: status,
    delay: delete_time,
    timestamp: Date.now(),
  };
  sessionStorage.setItem("pendingToast", JSON.stringify(toastData));
}

function handleRedirect(response) {
  if (response.status === 302) {
    window.location.href = response.headers[0][1];
    return true;
  }
  return false;
}

function handleDomUpdate(response, element) {
  const selector = element.getAttribute("data-selector");
  if (selector && response.html_content) {
    document.querySelector(selector).innerHTML = response.html_content;
    return true;
  } else if (response.json_content?.target && response.json_content?.html) {
    document.querySelector(response.json_content.target).innerHTML =
      response.json_content.html;
    return true;
  }
  return false;
}

function handleHtmlToast(response, element) {
  if (element.hasAttribute("data-sendtoast")) {
    let delay = element.getAttribute("data-delay") || 2000;
    const parser = new DOMParser();
    const toast_element = parser.parseFromString(
      response.html_content,
      "text/html"
    ).body.firstChild;
    document.querySelector(".toast-container").appendChild(toast_element);
    setTimeout(() => {
      toast_element.remove();
    }, delay);
    return true;
  }
  return false;
}

function handleJsonToast(response, element) {
  if (element.hasAttribute("data-toast")) {
    let delay = element.getAttribute("data-delay") || 2000;

    if (response.json_content?.content?.[0]?.errormessage) {
      send_toast(
        response.json_content.content[0].errormessage,
        "warning",
        "",
        delay
      );
    } else if (response.json_content?.content?.[0]?.text) {
      const status = response.json_content.success ? "success" : "warning";
      send_toast(response.json_content.content[0].text, status, "", delay);
    } else if (response.json_content?.message) {
      const status = response.json_content.success ? "success" : "warning";
      send_toast(response.json_content.message, status, "", delay);
    } else if (response.json_content?.error) {
      send_toast(response.json_content.error, "warning", "", delay);
    } else if (response.json_content?.success === true) {
      send_toast("Wijziging succesvol opgeslagen", "success", "", delay);
    }
    return true;
  }
  return false;
}

function handleRefresh(response, element) {
  const to_refresh = element.hasAttribute("data-refresh");
  if (to_refresh) {
    storePendingToast(response, element);
    window.location.reload();
    return true;
  }
  return false;
}

function handleBackendReload(response, element) {
  if (response.json_content?.reload) {
    storePendingToast(response, element);
    window.location.reload();
    return true;
  }
  return false;
}

function ws_request(event, endpoint) {
  sendWsRequest(endpoint, event.target).then((response) => {
    if (handleRedirect(response)) {
      return;
    }

    let did_something = false;
    did_something ||= handleRefresh(response, event.target);
    did_something ||= handleDomUpdate(response, event.target);
    did_something ||= handleHtmlToast(response, event.target);
    did_something ||= handleJsonToast(response, event.target);

    if (handleBackendReload(response, event.target)) {
      return;
    }

    if (!did_something) {
      console.log("Response:", response);
    }
  });
}

function sendWsRequest(endpoint, element) {
  console.log("Sending request to", endpoint);
  return new Promise((resolve, reject) => {
    const requestId = Math.random().toString(36).substring(2, 15);
    let attributes = {};
    for (let attribute of element.attributes) {
      attributes[attribute.name] = attribute.value;
    }
    if (element.type === "checkbox") {
      attributes["checked"] = element.checked;
    }
    if (element.value !== undefined) {
      attributes["value"] = element.value;
    }
    if (element.closest("form")) {
      let form_element = element.closest("form");
      let form_data = new FormData(form_element);
      for (let [key, value] of form_data.entries()) {
        attributes[key] = value;
      }
    }
    const message = JSON.stringify({ requestId, endpoint, attributes });
    showLoading();
    requestMap.set(requestId, (response) => {
      console.log(`Response from ${endpoint}:`, response);

      if (response.json_content) {
        console.log(`JSON content for ${endpoint}:`, response.json_content);
      }
      resolve(response);
    });
    ws.send(message);
  });
}

function send_toast(body, status = "default", title = "", delete_time = 2000) {
  const alertConfigs = {
    success: { icon: "fas fa-check-circle", alertClass: "alert-success" },
    danger: { icon: "fas fa-exclamation-triangle", alertClass: "alert-danger" },
    warning: {
      icon: "fas fa-exclamation-triangle",
      alertClass: "alert-warning",
    },
    info: { icon: "fas fa-info-circle", alertClass: "alert-info" },
    default: { icon: "fas fa-info-circle", alertClass: "alert-primary" },
  };

  const { icon, alertClass } = alertConfigs[status] || alertConfigs.default;

  let toast_container = document.querySelector(".toast-container");
  if (!toast_container) {
    console.error("Toast container not found");
    return;
  }

  let toast = document.createElement("div");
  toast.className = `alert ${alertClass} alert-dismissible show mt-2`;
  toast.style.pointerEvents = "auto";
  toast.innerHTML = `
        ${title
      ? `<span class="alert-heading"><i class="${icon}"></i>${title}</span><p class="mb-0">${body}</p>`
      : `<i class="${icon}"></i> <span>${body}</span>`
    }
        <button type="button" style="display: flex;" onclick="this.parentElement.remove()"><img src="/static/css/icons/close_alert.svg" alt="Close"></button>
    `;

  toast_container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, delete_time);
}

function checkAndShowPendingToast() {
  const pendingToastData = sessionStorage.getItem("pendingToast");
  if (pendingToastData) {
    try {
      const toastData = JSON.parse(pendingToastData);

      const now = Date.now();
      const age = now - toastData.timestamp;

      if (age < 10000) {

        setTimeout(() => {
          send_toast(toastData.message, toastData.status, toastData.title, toastData.delay);
        }, 100);
      }
      sessionStorage.removeItem("pendingToast");
    } catch (error) {
      console.error("Error displaying pending toast:", error);
      sessionStorage.removeItem("pendingToast");
    }
  }
}


function set_redis_option(event) {
  sendWsRequest("/settings/set-redis-option/", event.target).then((response) => {
    send_toast(response.json_content?.message, "success");
  });
}

function set_redis_option_with_reload(event) {
  sendWsRequest("/settings/set-redis-option/", event.target).then((response) => {
    window.location.reload();
  });
}

function set_printnode_printers(event) {
  sendWsRequest("/instellingen/set-printnode-printers/", event.target).then((response) => {
    send_toast(response.json_content?.message, "success");
  });
}


async function showRemoveToast(event) {
  const routing = event.target.getAttribute("data-routing");
  const session_name = event.target.getAttribute("data-session");

  const functionName = event.target.getAttribute("data-functionName");
  const routingName = event.target.getAttribute("data-routingName");
  const extra_data = event.target.getAttribute("data-extra_data");

  const toastContainer = document.querySelector(".toast-container");
  if (!toastContainer) {
    console.error("Toast container not found");
    return;
  }

  let amount;
  let removelist;

  if (routing && session_name) {
    const response = await sendWsRequest(routing, event.target);
    const sessionContent = response.json_content.session_content;
    amount = sessionContent.length;
  } else {
    const checkedItems = document.querySelectorAll(".single-checkbox:checked");
    amount = checkedItems.length;
    removelist = Array.from(checkedItems)
      .map((item) => item.getAttribute("data-removal_element"))
      .join(",");
  }

  if (amount === 0) {
    console.log("No items selected to remove.");
    return;
  }

  const toast = document.createElement("div");
  toast.className = `alert alert-danger alert-dismissible show mt-2`;
  toast.style.pointerEvents = "auto";
  toast.innerHTML = `
        <span class="alert-heading"><i class="fas fa-exclamation-triangle"></i>Waarschuwing</span>
        <p>${amount} item(s) verwijderen?</p>
        <br>
        <button
            data-function="click->${functionName}"
            data-routing="${routingName}"
            data-removelist="${removelist}"
            ${extra_data}
            class="btn btn-primary mt-2"
            onclick="this.parentElement.remove()">
            Ja
        </button>
        <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
    `;
  toastContainer.appendChild(toast);

  // Automatically remove the toast after a delay (optional)
  setTimeout(() => {
    toast.remove();
  }, 5000); // Show for 5 seconds if not confirmed
}

function showConfirmationToast(event, text, extra_data) {
  const functionName = event.currentTarget.getAttribute("data-functionName");
  const routingName = event.currentTarget.getAttribute("data-routing");

  const toastContainer = document.querySelector(".toast-container");
  if (!toastContainer) {
    console.error("Toast container not found");
    return;
  }
  const toast = document.createElement("div");
  toast.className = `alert alert-warning alert-dismissible show mt-2`;
  toast.style.pointerEvents = "auto";
  toast.innerHTML = `
        <span class="alert-heading"><i class="fas fa-exclamation-triangle"></i>Waarschuwing</span>
        <p>${text}</p>
        <button
            data-function="click->${functionName}"
            data-routing="${routingName}"
            ${extra_data}
            class="btn btn-primary mt-2"
            onclick="this.parentElement.remove()">
            Ja
        </button>
        <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
    `;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 10000); // Show for 5 seconds if not confirmed
}

document.addEventListener("DOMContentLoaded", (e) => {
  // Check for and display any pending toast messages from before page refresh
  checkAndShowPendingToast();

  for (const element of Array.from(
    document.querySelectorAll("[data-endpoint], [data-function]")
  )) {
    handle_attribute(
      element,
      element.getAttributeNode("data-endpoint") ||
      element.getAttributeNode("data-function")
    );
  }

  window.mutationObserver = new MutationObserver((mutations) =>
    process_mutations(mutations)
  );
  window.mutationObserver.observe(document, {
    attributes: true,
    childList: true,
    subtree: true,
  });

  // Add click handler for document
  document.addEventListener("click", function (event) {
    const searchResults = document.querySelector("#search-results");
    const searchInput = document.querySelector("#global-search-input");
    const searchInputContainer = document.querySelector("#global-search-form");

    if (searchResults && searchInput) {
      // Check if click is outside both search results and search input
      if (
        !searchResults.contains(event.target) &&
        (!searchInputContainer || !searchInputContainer.contains(event.target))
      ) {
        searchResults.innerHTML = "";
        searchInput.value = "";
      }
    }
  });

  document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
      for (const modal of document.querySelectorAll('.custom-modal')) {
        if (modal.style.display === 'block') {
          hide_modal(modal.id);
        }
      }
    }
  });

  document.addEventListener('click', function(event) {
    if (event.target.classList.contains('custom-modal-overlay')) {
      hide_modal(event.target.closest('.custom-modal').id);
    }
  });

  document.addEventListener('click', function(event) {
    if (event.target.classList.contains('siu-modal')) {
      hide_modal(event.target.closest('.siu-modal').id);
    }
  });

  const is_collapsed = localStorage.getItem("sidebar_collapsed") === "true"
  const sidebar = document.getElementById("sidebar")
  if (sidebar) {
    if (is_collapsed) {
      sidebar.classList.add("collapse");
      sidebar.classList.remove("show");
    }
    else {
      sidebar.classList.add("show");
      sidebar.classList.remove("collapse");
    }
  }

});

function toggleAllCheckboxes(event) {
  const masterCheckbox = event.currentTarget;
  const isChecked = masterCheckbox.checked;
  const productCheckboxes = document.querySelectorAll(".single-checkbox");

  // Client-side visual sync for currently visible checkboxes
  productCheckboxes.forEach((checkbox) => {
    checkbox.checked = isChecked;
  });

  // Backend call to update session for all groups and morph button & master checkbox
  // masterCheckbox already has data-routing, data-target1, data-target2, and data-repricer_group_id="all"
  if (masterCheckbox.hasAttribute("data-routing")) {
    handle_and_morph_multi(event);
  } else {
    // This else block might be redundant if data-routing is always present as expected.
    console.warn(
      "Master checkbox toggled, but data-routing attribute is missing for backend update."
    );
  }
}

function checkAllCheckboxes(event) {
  const singleCheckboxElement = event.currentTarget;

  // Backend call to update session for this specific group
  // singleCheckboxElement has data-routing, data-target, and its specific data-repricer_group_id
  if (singleCheckboxElement.hasAttribute("data-routing")) {
    handle_and_morph(event);
  }
  // Client-side master checkbox visual sync
  // This part runs after an individual click (after its handle_and_morph is initiated)
  const allCheckbox = document.getElementById("all-checkbox");
  const productCheckboxes = document.querySelectorAll(".single-checkbox");
  if (allCheckbox && productCheckboxes.length > 0) {
    const allCurrentlyChecked = Array.from(productCheckboxes).every(
      (checkbox) => checkbox.checked
    );
    allCheckbox.checked = allCurrentlyChecked;
  }
}

function updateStarVisuals(container, value) {
  const stars = container.querySelectorAll('.star-rating-item');
  stars.forEach(s => {
    const starValue = parseInt(s.getAttribute('data-value') || s.getAttribute('value'));
    if (starValue <= value) {
      s.classList.remove('siu-star-hover_off');
      s.classList.add('siu-star-filled-hover_off');
    } else {
      s.classList.remove('siu-star-filled-hover_off');
      s.classList.add('siu-star-hover_off');
    }
  });
}

function handleStarHover(event) {
  const starElement = event.currentTarget;
  const container = starElement.closest('.star-rating-container');
  if (!container) return;
  const hoverValue = parseInt(starElement.getAttribute('data-value') || starElement.getAttribute('value'));
  updateStarVisuals(container, hoverValue);
}

function handleStarClick(eventOrElement) {
  const starElement = eventOrElement.currentTarget ? eventOrElement.currentTarget : eventOrElement;
  const container = starElement.closest('.star-rating-container');
  if (!container) return;

  const clickedValue = parseInt(starElement.getAttribute('data-value') || starElement.getAttribute('value'));
  const hiddenInput = container.querySelector('input[type="hidden"]');

  // Update hidden input value
  if (hiddenInput) {
      hiddenInput.value = clickedValue;
  }
  // Update the container's data-current-value for hover reset logic
  container.dataset.currentValue = clickedValue;

  // Update visuals
  updateStarVisuals(container, clickedValue);
}


function handleStarContainerLeave(event) {
  const container = event.currentTarget;
  const resetValue = parseInt(container.dataset.currentValue) || 0;
  updateStarVisuals(container, resetValue);
}

// function handleStarHover() {
//     const starContainers = document.querySelectorAll('.star-rating-container');
//     console.log('starContainers', starContainers);
//     if (starContainers.length === 0) return;

//     starContainers.forEach(container => {
//         const stars = container.querySelectorAll('.star-rating-item');
//         // Determine the actual current value for this specific container
//         // Option A: Count initially filled stars
//         // let currentValue = 0;
//         // stars.forEach(s => {
//         //     if (s.classList.contains('siu-star-filled')) {
//         //         currentValue = parseInt(s.getAttribute('value'));
//         //     }
//         // });
//         // Option B: Try reading hidden input if it exists (modal context)
//         const hiddenInput = container.querySelector('input[type="hidden"]');
//         let currentValue = hiddenInput ? parseInt(hiddenInput.value) : 0;
//          // Option C: If hiddenInput not found, count filled stars (group context)
//          if (!hiddenInput) {
//              stars.forEach(s => {
//                  if (s.classList.contains('siu-star-filled')) {
//                      currentValue = Math.max(currentValue, parseInt(s.getAttribute('value')));
//                  }
//              });
//          }

//         // 2. Store the current value on the container for mouseleave
//         container.setAttribute('data-current-value', currentValue);

//         // Remove existing listeners to prevent duplicates if called multiple times
//         stars.forEach(star => {
//             star.replaceWith(star.cloneNode(true)); // Simple way to remove all listeners
//         });
//         // Re-select stars after cloning
//         const freshStars = container.querySelectorAll('.star-rating-item');

//         // Add mouseenter listeners to fresh stars
//         freshStars.forEach(star => {
//             star.addEventListener('mouseenter', function() {
//                 const hoverValue = parseInt(this.getAttribute('value'));
//                 // Update stars within this specific container
//                 freshStars.forEach(s => {
//                     const starValue = parseInt(s.getAttribute('value'));
//                     if (starValue <= hoverValue) {
//                         s.classList.remove('siu-star-hover_off');
//                         s.classList.add('siu-star-filled', 'text-warning'); // Ensure warning color on hover
//                     } else {
//                         s.classList.remove('siu-star-filled', 'text-warning');
//                         s.classList.add('siu-star-hover_off');
//                     }
//                 });
//             });
//         });

//          // Remove existing container listener before adding a new one
//         container.replaceWith(container.cloneNode(true)); // Clone container to remove its listeners
//         const freshContainer = document.querySelector(`[data-current-value="${currentValue}"]`); // Re-select fresh container - might need better selector
//         // If re-selection is problematic, attach listener to original container *before* cloning stars

//         // Add mouseleave listener to the container
//         freshContainer.addEventListener('mouseleave', function() {
//             // Use the stored current value
//             const resetValue = parseInt(this.getAttribute('data-current-value'));
//             const starsToReset = this.querySelectorAll('.star-rating-item'); // Select stars within *this* container

//             // Reset stars to match the stored current value
//             starsToReset.forEach(s => {
//                 const starValue = parseInt(s.getAttribute('value'));
//                 if (starValue <= resetValue) {
//                     s.classList.remove('siu-star-hover_off');
//                     s.classList.add('siu-star-filled', 'text-warning'); // Ensure warning color
//                 } else {
//                     s.classList.remove('siu-star-filled', 'text-warning');
//                     s.classList.add('siu-star-hover_off');
//                 }
//             });
//         });

//     });
// }

function toggle_edit_mode(event) {
  const toggleId = event.currentTarget.getAttribute("data-editfield");
  const displayView = document.getElementById(toggleId);
  const editView = document.getElementById(`${toggleId}-edit`);

  // Toggle visibility
  if (displayView.style.display !== "none") {
    displayView.style.setProperty("display", "none", "important");
    editView.style.setProperty("display", "flex", "important");
    // Focus on the input field
    const input = editView.querySelector("input");
    if (input) {
      input.focus();
      input.select();
    }
  }
}

function handle_file_select(event) {
  const fileInput = document.getElementById("id_file");
  if (fileInput) {
    fileInput.click();

    // Update the filename display when a file is selected
    fileInput.addEventListener("change", function () {
      const fileNameElement = document.querySelector(".file-name");
      if (fileNameElement) {
        if (this.files.length > 0) {
          fileNameElement.textContent = this.files[0].name;

          // Enable the import button if it exists
          const importButton = document.getElementById("import-button");
          if (importButton) {
            importButton.disabled = false;
          }
        } else {
          fileNameElement.textContent = "Geen bestand gekozen";
        }
      }
    });
  }
}

// PURE CLIENT FUNCTIONS START HERE

function fill_add_product(element) {
  document.getElementById("add_product_id").value = element.dataset.product;
  document.getElementById("filledresult").innerHTML = element.dataset.title;
  document.getElementById("product_searchresults").innerHTML = "";
}

let intervalId;
const showLoading = () => {
  const outerbar = document.querySelector("#outer-bar");
  if (outerbar) {
    const bar = document.createElement("div");
    bar.id = "inner-bar";
    bar.style.backgroundColor = "#00DD8D";
    bar.style.height = "2px";
    outerbar.appendChild(bar);
    intervalId = setInterval(move, 30);
    let width = 1;

    document.firstElementChild.style.cursor = "wait";

    function move() {
      if (width >= 100) {
        width = 1;
      } else {
        width++;
        bar.style.width = width + "%";
      }
    }
  }
};

const hideLoading = () => {
  clearInterval(intervalId);
  document.firstElementChild.style.cursor = "unset";
  const bar = document.querySelectorAll("#inner-bar");
  bar.forEach((b) => b.remove());
};

function show_notifications(event) {
  const targetElement = document.querySelector("#notifications-div");
  if (!targetElement.hidden) {
    targetElement.hidden = true;
    return;
  }
  targetElement.hidden = false;
  targetElement.innerHTML = `
        <div class="container mt-0">
            <div class="card" id="notification-card">
                <div class="card-body">
                    <h5 class="card-title">Meldingen</h5>
                    <div class="row">
                        <div class="col-auto mx-auto">
                            <div class="spinner-border text-primary" role="status">
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;

  sendWsRequest("/home/notifications/", targetElement).then((response) => {
    if (response.json_content?.target && response.json_content?.html) {
      document.querySelector(response.json_content.target).innerHTML =
        response.json_content.html;
    }
  });
}

function delete_all_notifications(event) {
  sendWsRequest("/home/notifications/delete/", event.target).then((response) => {
    if (response.json_content?.success) {
      const targetElement = document.querySelectorAll(".notification");
      targetElement.forEach((element) => {
        element.remove();
      });
    }
  });
}

function delete_notification(event) {
  const eventId = event.target.getAttribute("data-event-id");
  sendWsRequest(`/home/notifications/delete/${eventId}/`, event.target).then((response) => {
    if (response.json_content?.success) {
      event.target.closest(".notification").remove();
    }
  });
}

function global_search(event) {
  const query = event.target.value;
  if (!query || query.length === 0) {
    document.querySelector("#search-results").innerHTML = "";
    return;
  }

  sendWsRequest("/zoeken/", event.target).then((response) => {
    if (response.json_content?.html) {
      document.querySelector("#search-results").innerHTML =
        response.json_content.html;
    }
  });
}

function search(event) {
  const query = event.target.value;
  console.log("query", query);
  const target = event.target.getAttribute("data-target");
  const endpoint = event.target.getAttribute("data-routing");
  const keep_results = event.target.getAttribute("data-keep-results");
  console.log("endpoint", endpoint);
  if ((!query || query.length === 0) && !keep_results) {
    const targetElement = document.querySelector(target);
    if (targetElement) {
      targetElement.innerHTML = "";
    }
    return;
  }

  sendWsRequest(endpoint, event.target).then((response) => {
    if (target && response.json_content?.html) {
      document.querySelector(target).innerHTML = response.json_content.html;
    }
  });
}

function showMoreOrders(element) {
  const hiddenList = document.getElementById("hiddenList");
  if (hiddenList) {
    hiddenList.style.display = "block";
    element.style.display = "none";
  }
}

function search_all_orders(event) {
  // Remember if hidden list was visible
  const hiddenList = document.getElementById("hiddenList");
  const wasVisible = hiddenList && hiddenList.style.display === "block";

  sendWsRequest("/home/search_all_orders/", event.target).then((response) => {
    if (response.json_content?.target && response.json_content?.html) {
      document.querySelector(response.json_content.target).innerHTML =
        response.json_content.html;

      // If hidden list was visible before, show it again
      if (wasVisible) {
        const newHiddenList = document.getElementById("hiddenList");
        const newShowMore = document.getElementById("showMore");
        if (newHiddenList && newShowMore) {
          newHiddenList.style.display = "block";
          newShowMore.style.display = "none";
        }
      }
    }
  });
}

function toggleWebhook(event) {
  const salesChannelId = event.target.getAttribute("data-sales-channel-id");
  const endpoint = event.target.checked
    ? `/bol/webhooks/create/${salesChannelId}/`
    : `/bol/webhooks/delete/${salesChannelId}/`;
  console.log("endpoint", endpoint);

  // Send WebSocket request
  sendWsRequest(endpoint, event.target)
    .then((response) => {
      if (
        response.json_content?.content &&
        response.json_content?.content[0] &&
        response.json_content?.content[0]?.text
      ) {
        const status = response.success ? "success" : "warning";
        send_toast(response.json_content?.content[0]?.text, status); // Show toast for both success and error
      }

      // Update label text based on checkbox state
      const label = event.target.nextElementSibling;
      if (label && label.tagName.toLowerCase() === "label") {
        label.textContent = event.target.checked
          ? "Verwijder webhook"
          : "Maak webhook";
      }
      if (response.success) {
        console.log(
          `Webhook ${event.target.checked ? "enabled" : "disabled"
          } for sales channel ${salesChannelId}`
        );
      } else {
        console.error(
          `Error ${event.target.checked ? "enabling" : "disabling"} webhook:`,
          response.error
        );
      }
    })
    .catch((error) => {
      send_toast("WebSocket request failed", "warning"); // Show error toast if request fails
    });
}

function edit_value(event) {
  console.log("edit_value", event.target);
  const endpoint = event.target.getAttribute("data-routing");
  console.log("endpoint", endpoint);
  const toast = event.target.getAttribute("data-toast");
  sendWsRequest(endpoint, event.target)
    .then((response) => {
      console.log(response);
      if (response.json_content?.content[0]?.errormessage) {
        send_toast(response.json_content?.content[0]?.errormessage, "warning");
      } else if (toast && response.json_content?.content[0]?.text) {
        send_toast(response.json_content?.content[0]?.text, "success");
      }
    })
    .catch((error) => {
      send_toast("Fout tijdens het wijzigen van waarde", "warning");
    });
}

// function check_price_validity(event) {
//     console.log('check_price_validity', event.target);
//     const min_price = event.target.getAttribute('min');
//     const max_price = event.target.getAttribute('max');
//     sendWsRequest(endpoint, event.target).then(response => {
//         console.log(response);
//     });
// }

function toggle_repricer_group_standard_pricing(event) {
  console.log("toggle_repricer_group_standard_pricing", event.target);
  const repricer_group_id = event.target.getAttribute("data-repricer_group_id");
  const name = event.target.getAttribute("data-name");

  sendWsRequest(
    `/bol/repricer/v2/${repricer_group_id}/toggle/`,
    event.target
  ).then((response) => {
    console.log(response);

    const priceDiv = document.getElementById(name);

    if (response.json_content?.checked) {
      priceDiv.style.display = "none";
    } else {
      priceDiv.style.display = "block";
    }
  });
}

function toggle_repricer_standard_pricing(event) {
  console.log("toggle_repricer_standard_pricing", event.target);
  const repricer_id = event.target.getAttribute("data-repricer_id");
  const name = event.target.getAttribute("data-name");

  sendWsRequest(
    `/bol/repricer/v2/price/${repricer_id}/toggle/`,
    event.target
  ).then((response) => {
    console.log(response);

    const priceDiv = document.getElementById(`repricer-${name}`);

    if (response.json_content?.checked) {
      priceDiv.style.display = "none";
    } else {
      priceDiv.style.display = "block";
    }
  });
}

function toggle_repricer_group_margin_pricing(event) {
  console.log("toggle_repricer_group_margin_pricing", event.target);
  const repricer_group_id = event.target.getAttribute("data-repricer_group_id");

  sendWsRequest(
    `/bol/repricer/v2/${repricer_group_id}/toggle/`,
    event.target
  ).then((response) => {
    console.log(response);

    const marginPricingDiv = document.getElementById(
      "margin-pricing-container"
    );
    const minPriceDiv = document.getElementById("min-price-container");

    if (response.json_content?.checked) {
      marginPricingDiv.style.display = "block";
      minPriceDiv.style.display = "none";
    } else {
      marginPricingDiv.style.display = "none";
      minPriceDiv.style.display = "block";
    }
  });
}

function toggle_repricer_margin_pricing(event) {
  console.log("toggle_repricer_margin_pricing", event.target);
  const repricer_id = event.target.getAttribute("data-repricer_id");

  sendWsRequest(
    `/bol/repricer/v2/price/${repricer_id}/toggle/`,
    event.target
  ).then((response) => {
    console.log(response);

    const marginPricingDiv = document.getElementById(
      "repricer-margin-pricing-container"
    );
    const minPriceDiv = document.getElementById("repricer-min-price-container");

    if (response.json_content?.checked) {
      marginPricingDiv.style.display = "block";
      minPriceDiv.style.display = "none";
    } else {
      marginPricingDiv.style.display = "none";
      minPriceDiv.style.display = "block";
    }
  });
}

function toggle_repricer_group_price_stars(event) {
  console.log("toggle_repricer_group_price_stars", event.target);
  const repricer_group_id = event.target.getAttribute("data-repricer_group_id");

  sendWsRequest(
    `/bol/repricer/v2/${repricer_group_id}/toggle/`,
    event.target
  ).then((response) => {
    console.log(response);

    const priceStarsDiv = document.getElementById("price-stars-container");

    if (response.json_content?.checked) {
      priceStarsDiv.style.display = "block";
    } else {
      priceStarsDiv.style.display = "none";
    }
  });
}

function toggle_repricer_group_channel_price(event) {
  console.log("toggle_repricer_group_channel_price", event.target);
  const repricer_group_id = event.target.getAttribute("data-repricer_group_id");

  sendWsRequest(
    `/bol/repricer/v2/${repricer_group_id}/toggle/`,
    event.target
  ).then((response) => {
    console.log(response);

    const priceStarsDiv = document.getElementById("channel-price-container");
    const maxPriceDiv = document.getElementById("max-price-container");

    if (response.json_content?.checked) {
      priceStarsDiv.style.display = "block";
      maxPriceDiv.style.display = "none";
    } else {
      priceStarsDiv.style.display = "none";
      maxPriceDiv.style.display = "block";
    }
  });
}

function toggle_repricer_group_default_priority(event) {
  console.log("toggle_repricer_group_default_priority", event.target);
  const repricer_group_id = event.target.getAttribute("data-repricer_group_id");

  sendWsRequest(
    `/bol/repricer/v2/${repricer_group_id}/toggle/`,
    event.target
  ).then((response) => {
    console.log(response);

    const channelPrioritiesDiv = document.getElementById("channel-priorities");

    console.log("channelPrioritiesDiv", channelPrioritiesDiv);

    if (response.json_content?.checked) {
      channelPrioritiesDiv.style.display = "none";
    } else {
      channelPrioritiesDiv.style.display = "block";
    }
  });
}

function set_stars(event) {
  const starContainer = event.currentTarget.closest(".star-rating-container");
  const selectedValue = parseInt(event.currentTarget.getAttribute("value"));
  const endpoint = event.currentTarget.getAttribute("data-routing");

  starContainer.setAttribute("data-price_stars", selectedValue);

  // Send request to update the value
  sendWsRequest(endpoint, event.target).then((response) => {
    console.log(response);
  });
}

function bol_repricer_channel_priorities(event) {
  console.log("bol_repricer_channel_priorities", event.target);
  const country = event.target.getAttribute("data-country");
  const endpoint = event.target.getAttribute("data-routing");
  console.log("endpoint", endpoint);

  sendWsRequest(endpoint, event.target)
    .then((response) => {
      console.log(response);

      const updatedHtml = response.json_content?.html;
      console.log("updatedHtml", updatedHtml);

      if (country) {
        const channelPrioritiesContainer = document.querySelector(
          `#${country}-channel-priorities`
        );
        channelPrioritiesContainer.innerHTML = updatedHtml;
      } else {
        const channelPrioritiesContainer =
          document.querySelector(`#channel-priorities`);
        channelPrioritiesContainer.innerHTML = updatedHtml;
      }

      send_toast(response.json_content?.content[0]?.text, "success");
    })
    .catch((error) => {
      send_toast("Fout tijdens het wijzigen van waarde", "warning");
    });
}

function handle_and_toast(event) {
  const endpoint = event.currentTarget.getAttribute("data-routing");
  sendWsRequest(endpoint, event.currentTarget)
    .then((response) => {
      send_toast(response.json_content?.content[0]?.text, "success");
    })
    .catch((error) => {
      send_toast("Fout tijdens het verwerken van deze actie", "warning");
    });
}

function handle_and_morph(event) {
  if (event.type !== "keydown" || event.key == "Enter") {
    // Failsafe: Remove any existing modal overlays before creating a new one
    const existingOverlays = document.querySelectorAll(".modal-overlay");
    existingOverlays.forEach((overlay) => overlay.remove());

    console.log("handle_and_morph", event.currentTarget);
    const target = event.currentTarget.getAttribute("data-target");
    const endpoint = event.currentTarget.getAttribute("data-routing");
    console.log("target", target);
    console.log("endpoint", endpoint);
    sendWsRequest(endpoint, event.currentTarget)
      .then((response) => {
        document.querySelector(target).innerHTML = response.json_content?.html;
      })
      .catch((error) => {
        console.error("error", error);
        send_toast("Fout tijdens het verwerken van deze actie", "warning");
      });
  }
}

function handle_and_morph_multi(event) {
  if (event.type !== "keydown" || event.key == "Enter") {
    console.log("handle_multi_morph_attributes", event.currentTarget);
    const element = event.currentTarget;
    const endpoint = element.getAttribute("data-routing");
    console.log("endpoint", endpoint);

    // Find all data-target attributes and store selectors in order
    const targets = [];
    let i = 1;
    while (true) {
      const selector = element.getAttribute(`data-target${i}`);
      if (selector) {
        targets.push(selector);
        i++;
      } else {
        break; // Stop when data-targetN is not found
      }
    }
    console.log("Found targets:", targets);

    if (!endpoint || targets.length === 0) {
      console.warn("No endpoint or data-target[n] attributes found.");
      return;
    }

    sendWsRequest(endpoint, element)
      .then((response) => {
        // Expecting response.json_content.htmls to be an array
        const htmls = response.json_content?.htmls;

        if (Array.isArray(htmls)) {
          if (htmls.length !== targets.length) {
            console.warn(
              `Mismatch between number of targets (${targets.length}) and received HTMLs (${htmls.length}). Applying matching ones.`
            );
            // We'll still try to apply based on index matching
          }

          targets.forEach((selector, index) => {
            if (index < htmls.length) {
              // Ensure we have HTML for this target index
              const html = htmls[index];
              const targetElement = document.querySelector(selector);
              if (targetElement) {
                console.log(`Morphing target ${index + 1} (${selector})`);
                targetElement.innerHTML = html;
              } else {
                console.warn(
                  `Target element not found for selector: ${selector}`
                );
              }
            }
          });
        } else {
          console.error(
            "Invalid htmls structure received (expected array):",
            htmls
          );
          send_toast("Fout tijdens het verwerken van de response", "warning");
        }
      })
      .catch((error) => {
        console.error("error", error);
        send_toast("Fout tijdens het verwerken van deze actie", "warning");
      });
  }
}

// --- Generic hover panel utilities bound via data-function ---
function show_hover_panel(event) {
  var anchor = event.currentTarget;
  var divId = anchor.getAttribute('data-target');
  var panel = document.getElementById(divId);
  if (!panel) return;

  var gap = 8;

  panel.style.display = 'block';
  panel.style.visibility = 'hidden';

  var iconRect = anchor.getBoundingClientRect();
  var tooltipRect = panel.getBoundingClientRect();

  var spaceRight = window.innerWidth - iconRect.right;
  var spaceLeft = iconRect.left;

  var needed = tooltipRect.width + gap;
  var side = 'right';
  if (spaceRight >= needed) {
    side = 'right';
  } else if (spaceLeft >= needed) {
    side = 'left';
  } else {
    side = spaceRight >= spaceLeft ? 'right' : 'left';
  }
  panel.setAttribute('data-side', side);

  panel.style.visibility = 'visible';
}

function hide_hover_panel(event) {
  var anchor = event.currentTarget;
  var divId = anchor.getAttribute('data-target');
  var panel = document.getElementById(divId);
  if (panel) panel.style.display = 'none';
}

function check_and_add_product_to_repricer_group(event) {
  console.log("check_and_add_product_to_repricer_group", event.currentTarget);
  const repricer_group_id = event.currentTarget.getAttribute(
    "data-repricer_group_id"
  );
  const product_id = event.currentTarget.getAttribute("data-product_id");

  const originalCurrentTarget = event.currentTarget;

  console.log("repricer_group_id", repricer_group_id);
  console.log("product_id", product_id);
  sendWsRequest(
    `/bol/repricer/v2/${repricer_group_id}/products/check/`,
    event.currentTarget
  ).then((response) => {
    console.log(response);
    // Set the currentTarget property before passing the event
    const eventProxy = new Proxy(event, {
      get: function (target, prop) {
        // Return the original element when currentTarget is accessed
        if (prop === "currentTarget") {
          return originalCurrentTarget;
        }
        // Otherwise return the original property
        return target[prop];
      },
    });
    if (response.json_content?.content[0]?.product_in_group) {
      const text = response.json_content?.content[0]?.text;
      const extra_data = `data-repricer_group_id='${repricer_group_id}' data-product_id='${product_id}' data-target='#repricers-table' data-bs-dismiss='modal'`;
      showConfirmationToast(eventProxy, text, extra_data);
    } else {
      handle_and_morph(eventProxy);
    }
  });
}

function showCustomConfirmationToast(event) {
  const customText = event.target.getAttribute("data-warning-text");
  const extraData = event.target.getAttribute("data-extra_data");

  showConfirmationToast(event, customText, extraData);
}

function show_modal(modal_id) {
  const modal = document.getElementById(modal_id);
  modal.style.display = 'block';
  document.body.style.overflow = 'hidden';
}

function show_modal_by_datafield(event) {
  const modal_id = event.target.getAttribute("data-modal");
  show_modal(modal_id);
}

function hide_modal(modal_id) {
  const modal = document.getElementById(modal_id);
  modal.style.display = 'none';
  document.body.style.overflow = 'auto';
}

function hide_modal_by_button_new(event) {
  hide_modal(event.target.closest('.siu-modal').id);
}
// Please deprecate
function hide_modal_by_button(event) {
  hide_modal(event.target.closest('.custom-modal').id);
}

function morphing_modal(event) {
  document.body.classList.add("modal-open");
  console.log("morphing_modal", event.target);
  const modalname = event.target.getAttribute("data-modal-name");
  const modal = document.getElementById(modalname);
  const endpoint = event.target.getAttribute("data-routing");
  if (modal) {
    modal.style.display = "flex";
  }
  sendWsRequest(endpoint, event.target).then((response) => {
    console.log(response);
    document.getElementById(`${modalname}-content`).innerHTML =
      response.json_content?.html;
  });
}

function show_delivery_time_modal(event) {
  document.body.classList.add("modal-open");
  document.getElementById("add-delivery-time-modal").style.display = "flex";
  sendWsRequest(
    `/voorraad/levertijden/${event.target.dataset.channel_id}/formulier/`,
    event.target
  ).then((response) => {
    document.getElementById("add-delivery-time-content").innerHTML =
      response.json_content.html;
  });
}

// A new, single-purpose function to clean everything up.
function close_all_modals_and_overlays() {
  const overlays = document.querySelectorAll(".modal-overlay");
  if (overlays.length > 0) {
    overlays.forEach((overlay) => overlay.remove());
  }

  const modals = document.querySelectorAll(
    '.siu-modal[style*="display: flex"]'
  );
  if (modals.length > 0) {
    modals.forEach((modal) => (modal.style.display = "none"));
  }

  document.body.classList.remove("modal-open");
}

// The original event handler, now restored and using the new cleanup function.
function close_modal(event) {
  if (
    event.target.classList.contains("siu-modal") ||
    event.target.classList.contains("siu-modal-close") ||
    event.target.dataset.modalclose ||
    event.target.closest(".siu-modal-close")
  ) {
    close_all_modals_and_overlays();
  }
}

// This function is likely still used somewhere. It can just call the cleanup function.
function close_modal_by_button(event) {
  close_all_modals_and_overlays();
}

function save_and_close_modal(event) {
  event.preventDefault();
  const element = event.currentTarget;
  const endpoint = element.getAttribute("data-routing");
  sendWsRequest(endpoint, element).then((response) => {
    close_all_modals_and_overlays(); // Use the new robust cleanup function
    if (response.json_content.status === "success") {
      send_toast(response.json_content.message, "success");
    } else {
      send_toast(response.json_content.message, "danger");
    }
  });
}

function add_delivery_time(event) {
  sendWsRequest(`/voorraad/levertijden/toevoegen/`, event.target).then(
    (response) => {
      if (response.json_content.success) {
        if (response.json_content.added_country_section) {
          const container = document.getElementById(
            `delivery-times-${response.json_content.channel_id}`
          );
          container.insertAdjacentHTML("beforeend", response.json_content.html);
        } else {
          document.getElementById(
            `delivery-times-${response.json_content.channel_id}-${response.json_content.country}`
          ).innerHTML = response.json_content.html;
        }
        document.getElementById("add-delivery-time-modal").style.display =
          "none";
      }
      // Might be nice, but the toasts arent good looking currently
      // send_toast('success', 'Levertijd toegevoegd', 3000);
    }
  );
}

function delete_delivery_time(event) {
  let country_container = event.currentTarget.closest(
    ".delivery-time-saleschannel-country-container"
  );
  let country_body = country_container.querySelector(
    ".delivery-time-saleschannel-country-body"
  );
  const delivery_time_id = event.currentTarget.dataset.delivery_time_id;
  sendWsRequest(
    `/voorraad/levertijden/${delivery_time_id}/verwijderen/`,
    event.target
  ).then((response) => {
    document.getElementById(
      `delivery-times-${response.json_content.channel_id}-${response.json_content.country}`
    ).innerHTML = response.json_content.html;
    if (country_body.children.length == 0) {
      country_container.remove();
    }
  });
}

function move_delivery_time(event) {
  const delivery_time_id = event.currentTarget.dataset.delivery_time_id;
  const direction = event.currentTarget.dataset.direction;
  sendWsRequest(
    `/voorraad/levertijden/${delivery_time_id}/wijzigen/`,
    event.currentTarget
  ).then((response) => {
    document.getElementById(
      `delivery-times-${response.json_content.channel_id}-${response.json_content.country}`
    ).innerHTML = response.json_content.html;
  });
}

function refresh_amazon_delivery_options(event) {
  sendWsRequest(`/voorraad/levertijden/amazon-verversen/`, event.target).then(
    (response) => {
      send_toast("success", "Amazon Levertijden ververst", 2000);
    }
  );
}

function get_amazon_delivery_options_for_country(event) {
  sendWsRequest(`/voorraad/levertijden/amazon-voor-land/`, event.target).then(
    (response) => {
      document.getElementById("amazon-delivery-options").innerHTML =
        response.json_content.delivery_options_html;
      document.getElementById("warehouse-options").innerHTML =
        response.json_content.warehouse_html;
    }
  );
}

function refresh_kaufland_delivery_options(event) {
  sendWsRequest(`/voorraad/levertijden/kaufland-verversen/`, event.target).then(
    (response) => {
      send_toast("success", "Kaufland Levertijden ververst", 2000);
    }
  );
}

// Helper function to read file as base64
function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      // reader.result is "data:<mime_type>;base64,<actual_base64_string>"
      // We only want the <actual_base64_string>
      const parts = reader.result.split(",");
      if (parts.length >= 2) {
        resolve(parts[1]);
      } else {
        reject(new Error("Invalid DataURL format for base64 extraction"));
      }
    };
    reader.onerror = (error) => reject(error);
    reader.readAsDataURL(file);
  });
}

async function handle_file_upload(event) {
  // Made async
  console.log("handle_file_upload initiated by:", event.target);
  const fileInput = document.getElementById("id_file"); // Always get the file input directly

  if (!fileInput) {
    console.error("File input with id 'id_file' not found.");
    return;
  }

  // Clear previous custom attributes to prevent stale data
  fileInput.removeAttribute("data-file-content-base64");
  fileInput.removeAttribute("data-actual-filename");

  if (fileInput.files && fileInput.files.length > 0) {
    const file = fileInput.files[0];
    console.log(
      `Reading file ${file.name} as base64 for handle_file_upload...`
    );
    const base64String = await readFileAsBase64(file);
    fileInput.setAttribute("data-file-content-base64", base64String);
    fileInput.setAttribute("data-actual-filename", file.name);
    console.log(
      `File attributes set on #id_file: data-actual-filename=${file.name}, data-file-content-base64 length=${base64String.length}`
    );

    const endpoint = fileInput.getAttribute("data-routing");
    sendWsRequest(endpoint, fileInput) // Pass fileInput so backend can get its attributes
      .then((response) => {
        const jsonData = response.json_content;
        console.log("handle_file_upload response:", jsonData);

        if (jsonData && jsonData.action === "show_conflict_modal") {
          const target = fileInput.getAttribute("data-target");
          console.log("target", target);
          const modalContentArea = document.getElementById(target);
          console.log("modalContentArea", modalContentArea);
          if (modalContentArea) {
            modalContentArea.innerHTML = jsonData.modal_html;
          }
        } else if (jsonData && jsonData.action === "reload") {
          if (jsonData.message) {
            send_toast(jsonData.message, "success");
          }
          setTimeout(
            () => {
              window.location.reload();
            },
            jsonData.message ? 1000 : 100
          ); // Longer delay if toast
        } else if (jsonData && jsonData.error) {
          send_toast(jsonData.error, "warning");
        }

        fileInput.removeAttribute("data-file-content-base64");
        fileInput.removeAttribute("data-actual-filename");
      });
  } else {
    console.log("No file selected in #id_file for handle_file_upload.");
  }
}

function handle_file_download(event) {
  const endpoint = event.currentTarget.getAttribute("data-routing");
  console.log("Downloading file from", endpoint);

  sendWsRequest(endpoint, event.currentTarget)
    .then((response) => {
      console.log("response", response);
      response = response.json_content;
      if (response.fileDownload && response.fileData) {
        console.log("response2", response);
        // Create a blob from the base64 data
        const binaryData = atob(response.fileData);
        const byteArray = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
          byteArray[i] = binaryData.charCodeAt(i);
        }
        const blob = new Blob([byteArray], { type: response.fileType });

        // Create a download link
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = response.fileName;

        // Trigger the download
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Optional: Show a toast notification
        if (
          response.content &&
          response.content[0] &&
          response.content[0].text
        ) {
          send_toast(response.content[0].text, "success");
        }
      } else if (response.error) {
        send_toast(response.error, "warning");
      }
    })
    .catch((error) => {
      console.error("Error downloading file:", error);
      send_toast("Fout tijdens het downloaden van bestand", "warning");
    });
}

function add_repricer_setting(event) {
  const settingType = event.currentTarget.getAttribute("data-setting_type");
  console.log("Adding new repricer setting of type:", settingType);

  // Create a new row
  const newRow = document.createElement("div");
  newRow.className = "repricer-price-row d-flex align-items-center mb-2";

  newRow.innerHTML = `
        <div class="d-flex align-items-center">
            <select class="form-select price-type-select me-2" data-function="change->change_price_type">
                <option value="handmatig" selected>Handmatig</option>
                <option value="winstmarge">Winstmarge</option>
                <option value="kanaal">Kanaal</option>
            </select>

            <div class="price-input-container">
                <input type="number" step="0.01" class="form-control me-2" value="0.00" placeholder="Prijs">
            </div>

            <button type="button" class="btn-close" data-function="click->remove_repricer_setting" aria-label="Verwijderen"></button>
        </div>
    `;

  // Find where to append the new row
  const addButton = event.currentTarget.closest(
    ".d-flex.justify-content"
  ).parentElement;
  addButton.parentElement.insertBefore(newRow, addButton);

  // Initialize event listeners for the new elements
  handle_attribute(
    newRow.querySelector(".price-type-select"),
    newRow.querySelector(".price-type-select").getAttributeNode("data-function")
  );

  handle_attribute(
    newRow.querySelector(".btn-close"),
    newRow.querySelector(".btn-close").getAttributeNode("data-function")
  );
}

function remove_repricer_setting(event) {
  const row = event.currentTarget.closest(".repricer-price-row");
  if (row) {
    row.remove();
  }
}

function change_price_type(event) {
  const selectedType = event.currentTarget.value;
  const container = event.currentTarget
    .closest(".repricer-price-row")
    .querySelector(".price-input-container");

  if (selectedType === "kanaal") {
    container.innerHTML = `
            <select class="form-select me-2">
                <option value="bol">Bol.com</option>
                <option value="amazon">Amazon</option>
                <!-- Add other channels as needed -->
            </select>
        `;
  } else {
    const placeholder = selectedType === "handmatig" ? "Prijs" : "Percentage";
    container.innerHTML = `
            <input type="number" step="0.01" class="form-control me-2" value="0.00" placeholder="${placeholder}">
        `;
  }
}

function handle_and_reload(event) {
  console.log("handle_and_reload", event.currentTarget);
  const element = event.currentTarget;
  const endpoint = element.getAttribute("data-routing");
  const toast = element.hasAttribute("data-toast"); // Check if the attribute exists

  sendWsRequest(endpoint, element)
    .then((response) => {
      console.log("handle_and_reload response:", response);
      const jsonData = response.json_content;

      // Show toast message from response if requested
      if (toast && jsonData?.content?.[0]?.text) {
        const status = jsonData.success ? "success" : "warning"; // Determine status from success flag
        send_toast(jsonData.content[0].text, status, "", 1500);
      }

      // Reload if requested
      if (jsonData?.reload === true) {
        // Add a small delay if toast was shown to allow user to see it
        setTimeout(
          () => {
            window.location.reload();
          },
          toast ? 500 : 0
        ); // 0 delay if no toast
      }
    })
    .catch((error) => {
      // Basic error handling from sendWsRequest's perspective
      console.error("handle_and_reload error:", error);
      send_toast("Fout tijdens het verwerken van deze actie", "warning");
    });
}

// --- Repricer Edit Modal JS ---

// function handleStarClick(eventOrElement) {
//   // Determine if input is event or element
//   const starElement = eventOrElement.currentTarget
//     ? eventOrElement.currentTarget
//     : eventOrElement;
//   if (!starElement) {
//     console.error("handleStarClick: Could not determine star element.");
//     return;
//   }

//   const container = starElement.closest(".star-rating-container");
//   if (!container) return;

//   const clickedValue = parseInt(
//     starElement.getAttribute("data-value") || starElement.getAttribute("value")
//   );
//   const hiddenInput = container.querySelector('input[type="hidden"]');
//   const stars = container.querySelectorAll(".star-rating-item");

//   // Update hidden input value
//   if (hiddenInput) {
//     hiddenInput.value = clickedValue;
//     // Optionally dispatch a change event if other JS relies on it
//     // hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
//   }

//   // Update visual state
//   stars.forEach((s) => {
//     const starValue = parseInt(
//       s.getAttribute("data-value") || s.getAttribute("value")
//     );
//     if (starValue <= clickedValue) {
//       s.classList.remove("siu-star-hover_off");
//       s.classList.add("siu-star-filled-hover_off");
//     } else {
//       s.classList.remove("siu-star-filled-hover_off");
//       s.classList.add("siu-star-hover_off");
//     }
//   });

//   // Update the container's data-current-value for hover reset logic
//   container.dataset.currentValue = clickedValue;
// }

function handleGroupStarClick(event) {
  const starElement = event.currentTarget;
  const clickedValue = parseInt(
    starElement.getAttribute("data-value") || starElement.getAttribute("value")
  );
  const endpoint = starElement.getAttribute("data-routing");
  const targetSelector = starElement.getAttribute("data-target"); // For potential morph on success

  if (!endpoint) {
    console.error("handleGroupStarClick: Missing data-routing attribute.");
    return;
  }

  // Send the request - Need to pass a dummy element or adapt sendWsRequest
  // Easiest is to pass the original element, sendWsRequest reads its attributes anyway
  sendWsRequest(endpoint, starElement) // Pass starElement, value is handled by explicit setting above if needed
    .then((response) => {
      // The morphing should happen based on the response from edit_price_value
      // if it returns HTML. edit_price_value currently returns simple success.
      // If we want morphing, edit_price_value needs to re-render the price rows.
      console.log("handleGroupStarClick response:", response);
      const jsonData = response.json_content;
      if (jsonData?.success) {
        // Optionally update stars visually immediately or rely on morph
        handleStarClick(starElement); // Pass the element directly
        if (jsonData.target) {
          const targetElement = document.querySelector(jsonData.target);
          if (targetElement) {
            targetElement.innerHTML = jsonData.html;
          }
        }
      } else {
        send_toast(
          jsonData?.content?.[0]?.errormessage || "Fout bij bijwerken",
          "warning"
        );
      }
    })
    .catch((error) => {
      console.error("handleGroupStarClick error:", error);
      send_toast("Fout bij bijwerken van sterren", "warning");
    });
}

function toggleMainValidityChoice(radioButton) {
  const section = radioButton.closest(".validity-section");
  if (!section) return;

  const category = radioButton.name.substring("validity_main_".length);
  const detailedOptionsContainer = section.querySelector(`#detailed-validity-options-${category}`);

  if (!detailedOptionsContainer) return;

  // Just show/hide - that's it!
  detailedOptionsContainer.style.display =
    radioButton.value === "limited" ? "block" : "none";
}

function toggleValidityInputs(radioButton) {
  // Find the parent validity section based on the radio button's name
  const section = radioButton.closest(".validity-section");
  if (!section) return;

  const category = radioButton.name.substring("validity_".length);

  const duurNumberInput = section.querySelector(
    `input[name="duration_value_${category}"]`
  );
  const duurUnitSelect = section.querySelector(
    `select[name="duration_unit_${category}"]`
  );
  const totDateInput = section.querySelector(
    `input[name="end_date_${category}"]`
  );

  if (!duurNumberInput || !duurUnitSelect || !totDateInput) {
    console.warn(
      "Could not find all required input fields in toggleValidityInputs for category:",
      category,
      section
    );
    return;
  }

  // Enable/disable inputs based on selected radio
  duurNumberInput.disabled = true;
  duurUnitSelect.disabled = true;
  totDateInput.disabled = true;

  if (radioButton.value === "duur") {
    duurNumberInput.disabled = false;
    duurUnitSelect.disabled = false;
  } else if (radioButton.value === "tot") {
    totDateInput.disabled = false;
  }
  // For 'onbepaalde', all remain disabled, which is the default set above.

  // Trigger initial sync after enabling/disabling
  // Pass the active radio button to syncValidityInputs to determine context
  syncValidityInputs({ currentTarget: radioButton, type: "radio_change" });
}

// --- Helper functions for date calculations ---
function _formatDateForInput(date) {
  if (!date || !(date instanceof Date) || isNaN(date)) {
    return "";
  }
  const year = date.getFullYear();
  const month = (date.getMonth() + 1).toString().padStart(2, "0");
  const day = date.getDate().toString().padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function _calculateEndDate(startDate, durationValue, durationUnit) {
  if (
    !(startDate instanceof Date) ||
    isNaN(startDate) ||
    durationValue === null ||
    durationValue === undefined ||
    durationValue === ""
  ) {
    return null;
  }
  const value = parseInt(durationValue);
  if (isNaN(value)) return null;

  let endDate = new Date(startDate); // Clone the start date

  if (durationUnit === "days") {
    endDate.setDate(endDate.getDate() + value);
  } else if (durationUnit === "weeks") {
    endDate.setDate(endDate.getDate() + value * 7);
  } else if (durationUnit === "months") {
    endDate.setMonth(endDate.getMonth() + value);
  } else {
    return null; // Unknown unit
  }
  return endDate;
}

function _calculateDuration(startDate, endDate) {
  if (
    !(startDate instanceof Date) ||
    isNaN(startDate) ||
    !(endDate instanceof Date) ||
    isNaN(endDate) ||
    endDate < startDate
  ) {
    return { value: "", unit: "days" }; // Return defaults if invalid input
  }

  let diffTime = Math.abs(endDate - startDate);
  let diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  // Try to fit into months (approx 30 days)
  if (diffDays >= 28) {
    // Use 28 for a bit of flexibility with month ends
    let diffMonths = Math.round(diffDays / 30.4375); // Average days in a month
    // Check if it's reasonably close to a whole number of months
    let datePlusMonths = new Date(startDate);
    datePlusMonths.setMonth(startDate.getMonth() + diffMonths);
    if (Math.abs(datePlusMonths - endDate) <= 1000 * 60 * 60 * 24 * 3) {
      // within 3 days
      if (diffMonths > 0) return { value: diffMonths, unit: "months" };
    }
  }
  // Try to fit into weeks
  if (diffDays >= 7) {
    let diffWeeks = Math.round(diffDays / 7);
    let datePlusWeeks = new Date(startDate);
    datePlusWeeks.setDate(startDate.getDate() + diffWeeks * 7);
    if (Math.abs(datePlusWeeks - endDate) <= 1000 * 60 * 60 * 24 * 1) {
      // within 1 day
      if (diffWeeks > 0) return { value: diffWeeks, unit: "weeks" };
    }
  }
  // Default to days
  return { value: diffDays, unit: "days" };
}
// --- End Helper functions ---

function syncValidityInputs(event) {
  const changedElement = event.currentTarget;
  const category =
    changedElement.getAttribute("data-category") ||
    changedElement.name.substring("validity_".length);
  const section = changedElement.closest(".validity-section");

  if (!section || !category) {
    console.warn(
      "syncValidityInputs: Could not find section or category.",
      changedElement
    );
    return;
  }

  const duurRadio = section.querySelector(
    `input[name="validity_${category}"][value="duur"]`
  );
  const totRadio = section.querySelector(
    `input[name="validity_${category}"][value="tot"]`
  );

  const duurNumberInput = section.querySelector(
    `input[name="duration_value_${category}"]`
  );
  const duurUnitSelect = section.querySelector(
    `select[name="duration_unit_${category}"]`
  );
  const totDateInput = section.querySelector(
    `input[name="end_date_${category}"]`
  );

  if (
    !duurRadio ||
    !totRadio ||
    !duurNumberInput ||
    !duurUnitSelect ||
    !totDateInput
  ) {
    console.warn(
      "syncValidityInputs: Missing one or more form elements in section for category:",
      category
    );
    return;
  }

  const today = new Date(); // Use current date as the start reference for calculations

  if (duurRadio.checked) {
    // "Duur" is active
    const durationValue = duurNumberInput.value;
    const durationUnit = duurUnitSelect.value;
    if (durationValue !== "") {
      // Only calculate if duration is set
      const endDate = _calculateEndDate(today, durationValue, durationUnit);
      if (endDate) {
        totDateInput.value = _formatDateForInput(endDate);
      } else {
        totDateInput.value = ""; // Clear if calculation fails
      }
    } else {
      // If duur value is cleared, clear the tot date as well
      // totDateInput.value = ""; // Optional: or leave as is
    }
  } else if (totRadio.checked) {
    // "Tot" is active
    const endDateStr = totDateInput.value;
    if (endDateStr) {
      const endDate = new Date(endDateStr);
      // Add time part to endDate to compare against today properly, and ensure it's valid
      if (!isNaN(endDate.getTime())) {
        // Adjust to local midnight to ensure correct day comparison
        endDate.setHours(0, 0, 0, 0);
        const todayMidnight = new Date(today);
        todayMidnight.setHours(0, 0, 0, 0);

        if (endDate >= todayMidnight) {
          const duration = _calculateDuration(todayMidnight, endDate);
          duurNumberInput.value = duration.value;
          duurUnitSelect.value = duration.unit;
        } else {
          // End date is in the past, clear duration or set to 0
          duurNumberInput.value = "";
          duurUnitSelect.value = "days";
        }
      } else {
        duurNumberInput.value = ""; // Invalid date input
        duurUnitSelect.value = "days";
      }
    } else {
      // If tot date is cleared, clear the duur inputs as well
      // duurNumberInput.value = ''; // Optional: or leave as is
      // duurUnitSelect.value = 'days'; // Optional: or leave as is
    }
  }
}

function handleModalRuleChange(event) {
  const element = event.currentTarget;
  const action = element.getAttribute("data-action");
  const targetSelector = element.getAttribute("data-target"); // e.g., #repricer-edit-min-rules-content
  const category = element.getAttribute("data-category"); // 'min' or 'max'
  const repricerId = element.getAttribute("data-repricer-id");
  const endpoint = `/bol/repricer/v2/${repricerId}/modal/update_rules/`; // Construct endpoint
  const targetElement = document.querySelector(targetSelector);

  if (!targetElement || !action || !category || !endpoint || !repricerId) {
    // Added repricerId check
    console.error("Missing data for modal rule change", {
      action,
      targetSelector,
      category,
      endpoint,
      repricerId,
    });
    return;
  }

  // Gather current rules *with values* from the target container
  const currentRules = [];
  targetElement
    .querySelectorAll(".repricer-price-row")
    .forEach((row, index) => {
      const rule = {};
      const typeSelect = row.querySelector(
        `select[name="price_type_${category}_${index}"]`
      );
      rule.price_type = typeSelect ? typeSelect.value : null;

      // Get value, checking for select or input or hidden (for stars)
      const valueElement = row.querySelector(
        `[name="price_value_${category}_${index}"]`
      );
      rule.price_value = valueElement ? valueElement.value : null;

      // --- Get validity info for this section ---
      // Validity is per section, not per row, get it from outside the loop
      // This is needed so backend has full context even if row list is empty initially
      // No need to add expires_at to individual rule objects here

      if (rule.price_type) {
        // Keep even pending for backend processing
        currentRules.push(rule);
      }
    });

  // --- MODIFICATION START: Temporarily add rules as attribute --- //
  const rulesAttributeName = `current_${category}_rules`;
  const rulesJson = JSON.stringify(currentRules);
  element.setAttribute(rulesAttributeName, rulesJson);
  // --- MODIFICATION END --- //

  // Send request with the constructed attributes
  sendWsRequest(endpoint, element) // Pass the element
    .then((response) => {
      // Pass attributes object
      if (response.json_content?.html !== undefined) {
        targetElement.innerHTML = response.json_content.html;
        // Re-initialize any JS needed within the new HTML? (e.g., date pickers if used)
      } else {
        send_toast("Fout bij bijwerken regels", "warning");
      }
    })
    .catch((error) => {
      console.error("Error updating modal rules:", error);
      send_toast("Kon regels niet bijwerken: Communicatiefout", "warning");
    })
    .finally(() => {
      // --- MODIFICATION START: Clean up temporary attribute --- //
      element.removeAttribute(rulesAttributeName);
      // --- MODIFICATION END --- //
    });
}

function save_repricer_rules_and_close_modal(event) {
  const saveButton = event.currentTarget;
  const modal = saveButton.closest(".siu-modal");
  const repricerId = saveButton.getAttribute("data-repricer_id");
  const endpoint = saveButton.getAttribute("data-routing");
  console.log(
    "save_repricer_rules_and_close_modal",
    saveButton,
    modal,
    repricerId,
    endpoint
  );
  // Find the actual modal content box, assuming it's within the modal
  const modalContentBox = modal.querySelector(".siu-modal-box"); // Or specific content container if available

  if (!modal || !repricerId || !endpoint || !modalContentBox) {
    console.error("Missing data for saving rules:", {
      modal,
      repricerId,
      endpoint,
      modalContentBox,
    });
    send_toast("Kon regels niet opslaan: Interne fout", "warning");
    return;
  }

  const minRules = [];
  const maxRules = [];

  // --- Gather Minimum Rules ---
  const minContainer = modalContentBox.querySelector(
    "#repricer-edit-min-rules-content"
  );
  if (minContainer) {
    // Get section-level validity
    const minValidity = {};

    // Check main validity choice first
    const mainValidityRadioMin = minContainer.querySelector(
      `input[name="validity_main_min"]:checked`
    );

    if (mainValidityRadioMin && mainValidityRadioMin.value === "unlimited") {
      minValidity.validity = "onbepaalde";
    } else {
      // Check detailed validity choice
      const validityRadioMin = minContainer.querySelector(
        `input[name="validity_min"]:checked`
      );
      minValidity.validity = validityRadioMin
        ? validityRadioMin.value
        : "onbepaalde"; // Default if somehow none checked
      if (minValidity.validity === "duur") {
        minValidity.duration_value = minContainer.querySelector(
          `input[name="duration_value_min"]`
        )?.value;
        minValidity.duration_unit = minContainer.querySelector(
          `select[name="duration_unit_min"]`
        )?.value;
      } else if (minValidity.validity === "tot") {
        minValidity.end_date = minContainer.querySelector(
          `input[name="end_date_min"]`
        )?.value;
      }
    }

    minContainer
      .querySelectorAll(".repricer-price-row")
      .forEach((row, index) => {
        const rule = {};
        const typeSelectMin = row.querySelector(
          `select[name="price_type_min_${index}"]`
        );
        rule.price_type = typeSelectMin ? typeSelectMin.value : null;
        const valueElementMin = row.querySelector(
          `[name="price_value_min_${index}"]`
        );
        rule.price_value = valueElementMin ? valueElementMin.value : null;
        // Add validity info to every rule for backend processing
        Object.assign(rule, minValidity);

        if (rule.price_type && rule.price_type !== "pending") {
          // Only add valid rules
          minRules.push(rule);
        }
      });
  }

  // --- Gather Maximum Rules ---
  const maxContainer = modalContentBox.querySelector(
    "#repricer-edit-max-rules-content"
  );
  if (maxContainer) {
    // Get section-level validity
    const maxValidity = {};

    // Check main validity choice first
    const mainValidityRadioMax = maxContainer.querySelector(
      `input[name="validity_main_max"]:checked`
    );

    if (mainValidityRadioMax && mainValidityRadioMax.value === "unlimited") {
      maxValidity.validity = "onbepaalde";
    } else {
      // Check detailed validity choice
      const validityRadioMax = maxContainer.querySelector(
        `input[name="validity_max"]:checked`
      );
      maxValidity.validity = validityRadioMax
        ? validityRadioMax.value
        : "onbepaalde";
      if (maxValidity.validity === "duur") {
        maxValidity.duration_value = maxContainer.querySelector(
          `input[name="duration_value_max"]`
        )?.value;
        maxValidity.duration_unit = maxContainer.querySelector(
          `select[name="duration_unit_max"]`
        )?.value;
      } else if (maxValidity.validity === "tot") {
        maxValidity.end_date = maxContainer.querySelector(
          `input[name="end_date_max"]`
        )?.value;
      }
    }

    maxContainer
      .querySelectorAll(".repricer-price-row")
      .forEach((row, index) => {
        const rule = {};
        const typeSelectMax = row.querySelector(
          `select[name="price_type_max_${index}"]`
        );
        rule.price_type = typeSelectMax ? typeSelectMax.value : null;
        const valueElementMax = row.querySelector(
          `[name="price_value_max_${index}"]`
        );
        rule.price_value = valueElementMax ? valueElementMax.value : null;
        // Add validity info to every rule for backend processing
        Object.assign(rule, maxValidity);

        if (rule.price_type && rule.price_type !== "pending") {
          // Only add valid rules
          maxRules.push(rule);
        }
      });
  }

  // --- MODIFICATION START: Temporarily add rules as attributes ---
  const minRulesJson = JSON.stringify(minRules);
  const maxRulesJson = JSON.stringify(maxRules);
  saveButton.setAttribute("min_rules", minRulesJson);
  saveButton.setAttribute("max_rules", maxRulesJson);
  // --- MODIFICATION END ---

  // Send request with the constructed attributes object
  sendWsRequest(endpoint, saveButton) // Pass the element
    .then((response) => {
      // Pass attributes object
      const jsonData = response.json_content;
      const status = jsonData?.success ? "success" : "warning";
      const message =
        jsonData?.content?.[0]?.text ||
        (jsonData?.success ? "Opgeslagen" : "Fout bij opslaan");
      send_toast(message, status);

      if (jsonData?.success) {
        // Close modal
        modal.style.display = "none";

        // --- MODIFIED: Morph specific cell --- //
        if (jsonData.target_id && jsonData.html !== undefined) {
          const targetElement = document.querySelector(
            `#${jsonData.target_id}`
          );
          if (targetElement) {
            targetElement.innerHTML = jsonData.html;
            // Removed row highlighting logic
          } else {
            console.warn(
              "Target cell not found for morphing:",
              jsonData.target_id
            );
            // Optionally fall back to reload if morph target is missing
            // window.location.reload();
          }
        }
        // --- End Modification --- //
      }
    })
    .catch((error) => {
      console.error("Error saving rules:", error);
      send_toast("Kon regels niet opslaan: Communicatiefout", "warning");
    })
    .finally(() => {
      // --- MODIFICATION START: Clean up temporary attributes ---
      saveButton.removeAttribute("min_rules");
      saveButton.removeAttribute("max_rules");
      // --- MODIFICATION END ---
    });
}

// --- End Repricer Edit Modal JS ---

function handleAddProductsWithConflictCheck(event) {
  console.log(
    "handleAddProductsWithConflictCheck initiated by:",
    event.currentTarget
  );
  const element = event.currentTarget;
  const endpoint = element.getAttribute("data-routing");
  const toast = element.hasAttribute("data-toast");

  sendWsRequest(endpoint, element).then((response) => {
    console.log("handleAddProductsWithConflictCheck response:", response);
    const jsonData = response.json_content;

    if (jsonData && jsonData.action === "show_conflict_modal") {
      let target = element.getAttribute("data-target");
      let modalContainer = document.getElementById(target);
      modalContainer.innerHTML = jsonData.modal_html;
    } else if (jsonData && jsonData.action === "reload") {
      if (toast && jsonData.message) {
        send_toast(jsonData.message, "success", "", 1500);
        setTimeout(() => {
          window.location.reload();
        }, 500); // Delay for toast
      } else {
        window.location.reload();
      }
    }
  });
}

function toggle_conflict_choice(event) {
  const clickedButton = event.currentTarget;
  const allChoiceButtons = document.querySelectorAll(".conflict-choice-button");

  allChoiceButtons.forEach((btn) => {
    btn.classList.remove("active");
    const icon = btn.querySelector("i.siu-icon");
    if (icon) {
      icon.classList.remove("icon-light-blue");
      icon.classList.add("icon-dark-blue");
    }
  });
  clickedButton.classList.add("active");
  const clickedIcon = clickedButton.querySelector("i.siu-icon");
  if (clickedIcon) {
    clickedIcon.classList.remove("icon-dark-blue");
    clickedIcon.classList.add("icon-light-blue");
  }
  handle_and_morph(event);
}

function toggle_and_handle(event) {
  toggle_button_active(event);
  const element = event.currentTarget;
  sendWsRequest(element.getAttribute("data-routing"), element).then(
    (response) => {
      console.log("toggle_and_handle response:", response);
    }
  );
}

function toggle_button_active(event) {
  const clickedButton = event.currentTarget;
  let button_group = clickedButton.getAttribute("data-button-group");
  const allChoiceButtons = document.querySelectorAll(`.${button_group}`);
  allChoiceButtons.forEach((btn) => {
    btn.classList.remove("active");
  });
  clickedButton.classList.add("active");
}

function add_supplier_row(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const endpoint = form.getAttribute("data-routing");
  const tableBodySelector = form.getAttribute("data-table-body");

  sendWsRequest(endpoint, form)
    .then((response) => {
      if (response.json_content && response.json_content.status === "success") {
        // Add the new row to the table
        const tableBody = document.querySelector(tableBodySelector);
        if (tableBody && response.json_content.new_row_html) {
          tableBody.insertAdjacentHTML(
            "beforeend",
            response.json_content.new_row_html
          );
        }

        // Clear the form
        form.reset();

        // Update the dropdown to remove the added supplier
        const supplierSelect = form.querySelector('select[name="supplier_id"]');
        const addedSupplierId = response.json_content.added_supplier_id;
        if (supplierSelect && addedSupplierId) {
          const optionToRemove = supplierSelect.querySelector(
            `option[value="${addedSupplierId}"]`
          );
          if (optionToRemove) {
            optionToRemove.remove();
          }
        }
      } else if (
        response.json_content &&
        response.json_content.status === "error"
      ) {
        send_toast(response.json_content.message, "danger");
      }
    })
    .catch((error) => {
      console.error("Error adding supplier:", error);
      send_toast(
        "Er is een fout opgetreden bij het toevoegen van de leverancier",
        "danger"
      );
    });
}

function toggle_sidebar() {
  const sidebar = document.getElementById("sidebar")
  const is_collapsed = sidebar.classList.contains("collapse")

  if (is_collapsed) {
    sidebar.classList.add("show");
    sidebar.classList.remove("collapse");
  }
  else {
    sidebar.classList.remove("show");
    sidebar.classList.add("collapse");
  }
  localStorage.setItem("sidebar_collapsed", !is_collapsed)
}

function create_api_key(event) {
  const button = event.currentTarget;

  // Collect checked sellers from checkboxes
  const checkedSellers = document.querySelectorAll('.seller-checkbox:checked');
  const sellerIds = Array.from(checkedSellers).map(cb => cb.value).join(',');

  // Check if permission elements exist (only for dev users)
  const devRoutesElement = document.getElementById('perm-dev_routes');
  const sellfillerRoutesElement = document.getElementById('perm-sellfiller_routes');
  const externalRoutesElement = document.getElementById('perm-external_routes');
  const thirdpartyRoutesElement = document.getElementById('perm-thirdparty_routes');
  const ownerSelectElement = document.getElementById('api-key-owner');

  // Get values only if elements exist
  const devRoutes = devRoutesElement ? devRoutesElement.checked : false;
  const sellfillerRoutes = sellfillerRoutesElement ? sellfillerRoutesElement.checked : false;
  const externalRoutes = externalRoutesElement ? externalRoutesElement.checked : false;
  const thirdpartyRoutes = thirdpartyRoutesElement ? thirdpartyRoutesElement.checked : false;
  const ownerUserId = ownerSelectElement ? ownerSelectElement.value : '';

  // Add data as attributes to the button
  button.setAttribute('seller_ids', sellerIds);
  button.setAttribute('dev_routes', devRoutes);
  button.setAttribute('sellfiller_routes', sellfillerRoutes);
  button.setAttribute('external_routes', externalRoutes);
  button.setAttribute('thirdparty_routes', thirdpartyRoutes);
  if (ownerUserId) {
    button.setAttribute('owner_user_id', ownerUserId);
  } else {
    button.removeAttribute('owner_user_id');
  }

  // Send via WebSocket using handle_and_morph
  handle_and_morph(event);
}
