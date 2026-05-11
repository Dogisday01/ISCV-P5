const API_PREFIX = "/api/v1";
const DEFAULT_LIMIT = 25;
const STATUS_FLOW = {
  open: ["assigned", "cancelled"],
  assigned: ["in_progress", "cancelled"],
  in_progress: ["completed"],
  completed: [],
  cancelled: [],
};
const ROLE_LABELS = {
  engineer: "Engineer",
  supervisor: "Supervisor",
  technical_admin: "Technical Admin",
};

const state = {
  accessToken: null,
  refreshToken: null,
  user: null,
  assets: [],
  requests: [],
  engineers: [],
  report: null,
  view: "overview",
  notice: null,
};

const dom = {
  heroPanel: document.querySelector("#hero-panel"),
  noticePanel: document.querySelector("#notice-panel"),
  workspaceRoot: document.querySelector("#workspace-root"),
  railNav: document.querySelector("#rail-nav"),
  sessionNote: document.querySelector("#session-note"),
};

function node(tagName, options = {}, children = []) {
  const element = document.createElement(tagName);
  // P4 frontend hardening point: render API data as text nodes instead of HTML sinks.
  if (options.className) {
    element.className = options.className;
  }
  if (options.text !== undefined) {
    element.textContent = options.text;
  }
  if (options.type) {
    element.setAttribute("type", options.type);
  }
  if (options.value !== undefined) {
    element.value = options.value;
  }
  if (options.placeholder) {
    element.setAttribute("placeholder", options.placeholder);
  }
  if (options.name) {
    element.setAttribute("name", options.name);
  }
  if (options.rows) {
    element.setAttribute("rows", String(options.rows));
  }
  if (options.id) {
    element.id = options.id;
  }
  if (options.attrs) {
    Object.entries(options.attrs).forEach(([key, value]) => {
      element.setAttribute(key, String(value));
    });
  }
  const childList = Array.isArray(children) ? children : [children];
  childList.flat().forEach((child) => {
    if (child === null || child === undefined) {
      return;
    }
    if (typeof child === "string") {
      element.append(document.createTextNode(child));
      return;
    }
    element.append(child);
  });
  return element;
}

function clear(element) {
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

function setNotice(tone, text) {
  state.notice = text ? { tone, text } : null;
  renderNotice();
}

function statusLabel(status) {
  return status.replaceAll("_", " ");
}

function actionLabel(status) {
  return {
    assigned: "Assign engineer",
    in_progress: "Start work",
    completed: "Complete work",
    cancelled: "Cancel request",
  }[status] || statusLabel(status);
}

function statusChip(status) {
  return node("span", {
    className: `status-chip status-${status}`,
    text: statusLabel(status),
  });
}

function roleLabel(role) {
  return ROLE_LABELS[role] || role;
}

function assetLookup() {
  return new Map(state.assets.map((asset) => [asset.id, asset]));
}

function engineerLookup() {
  return new Map(state.engineers.map((engineer) => [engineer.id, engineer]));
}

function assetSearchLabel(asset) {
  return `${asset.asset_tag} - ${asset.name} | ${asset.facility} | ${asset.equipment_type}`;
}

function renderAssetCell(assetId) {
  const asset = assetLookup().get(assetId);
  if (!asset) {
    return node("div", {}, [
      node("span", { className: "subtle-copy", text: "Unknown asset" }),
      node("code", { className: "technical-id", text: assetId }),
    ]);
  }
  return node("div", { className: "entity-cell" }, [
    node("strong", { text: `${asset.asset_tag} - ${asset.name}` }),
    node("span", { text: `${asset.facility} / ${asset.equipment_type}` }),
  ]);
}

function renderEngineerCell(engineerId) {
  if (!engineerId) {
    return node("span", { className: "subtle-copy", text: "Unassigned" });
  }
  const engineer = engineerLookup().get(engineerId);
  if (!engineer) {
    return node("div", {}, [
      node("span", { className: "subtle-copy", text: "Engineer not in current directory" }),
      node("code", { className: "technical-id", text: engineerId }),
    ]);
  }
  return node("div", { className: "entity-cell" }, [
    node("strong", { text: engineer.full_name }),
    node("span", { text: engineer.email }),
  ]);
}

function isPrivileged() {
  return state.user && state.user.role !== "engineer";
}

function allowedTransitions(item) {
  if (!state.user) {
    return [];
  }
  const base = STATUS_FLOW[item.status] || [];
  if (isPrivileged()) {
    return base.filter((status) => status === "assigned" || status === "cancelled");
  }
  if (item.assigned_engineer_id === state.user.id) {
    return base.filter((status) => status === "in_progress" || status === "completed");
  }
  return [];
}

async function readError(response, fallbackText) {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    return fallbackText;
  } catch {
    return fallbackText;
  }
}

async function refreshSession() {
  if (!state.refreshToken) {
    return false;
  }
  const response = await fetch(`${API_PREFIX}/auth/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: state.refreshToken }),
  });
  if (!response.ok) {
    clearSession();
    setNotice("warning", "Session expired. Sign in again to continue.");
    render();
    return false;
  }
  const payload = await response.json();
  state.accessToken = payload.access_token;
  state.refreshToken = payload.refresh_token;
  return true;
}

async function apiFetch(path, options = {}, retry = true) {
  const headers = new Headers(options.headers || {});
  // P4 frontend hardening point: access/refresh tokens live only in page memory.
  if (state.accessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${state.accessToken}`);
  }
  const response = await fetch(`${API_PREFIX}${path}`, { ...options, headers });
  if (response.status === 401 && retry && state.refreshToken && path !== "/auth/refresh") {
    const refreshed = await refreshSession();
    if (refreshed) {
      return apiFetch(path, options, false);
    }
  }
  return response;
}

async function loadWorkspace() {
  const meResponse = await apiFetch("/users/me");
  if (!meResponse.ok) {
    throw new Error(await readError(meResponse, "Unable to load current user"));
  }
  state.user = await meResponse.json();

  const requests = [
    apiFetch(`/assets?limit=${DEFAULT_LIMIT}`),
    apiFetch(`/maintenance-requests?limit=${DEFAULT_LIMIT}`),
  ];

  if (isPrivileged()) {
    requests.push(apiFetch(`/users?role=engineer&limit=${DEFAULT_LIMIT}`));
    requests.push(apiFetch(`/reports/maintenance-summary?limit=${DEFAULT_LIMIT}`));
  }

  const responses = await Promise.all(requests);
  const [assetsResponse, requestResponse, engineerResponse, reportResponse] = responses;
  if (!assetsResponse.ok) {
    throw new Error(await readError(assetsResponse, "Unable to load assets"));
  }
  if (!requestResponse.ok) {
    throw new Error(await readError(requestResponse, "Unable to load maintenance requests"));
  }

  state.assets = await assetsResponse.json();
  state.requests = await requestResponse.json();
  state.engineers = engineerResponse && engineerResponse.ok ? await engineerResponse.json() : [];
  state.report = reportResponse && reportResponse.ok ? await reportResponse.json() : null;
}

function clearSession() {
  state.accessToken = null;
  state.refreshToken = null;
  state.user = null;
  state.assets = [];
  state.requests = [];
  state.engineers = [];
  state.report = null;
  state.view = "overview";
}

async function login(email, password) {
  const formData = new URLSearchParams();
  formData.set("username", email);
  formData.set("password", password);
  const response = await fetch(`${API_PREFIX}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData.toString(),
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Login failed"));
  }
  const payload = await response.json();
  state.accessToken = payload.access_token;
  state.refreshToken = payload.refresh_token;
  await loadWorkspace();
}

async function logout() {
  if (state.refreshToken) {
    await fetch(`${API_PREFIX}/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    });
  }
  clearSession();
  setNotice("success", "Session closed.");
  render();
}

async function handleAssetCreate(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    asset_tag: form.asset_tag.value.trim(),
    name: form.name.value.trim(),
    facility: form.facility.value.trim(),
    equipment_type: form.equipment_type.value.trim(),
    location_detail: form.location_detail.value.trim() || null,
  };
  const response = await apiFetch("/assets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    setNotice("error", await readError(response, "Unable to register asset"));
    return;
  }
  form.reset();
  await loadWorkspace();
  setNotice("success", "Asset registered and ready for dispatch.");
  render();
}

async function handleRequestCreate(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const assetId = form.asset_id.value;
  if (!assetId) {
    setNotice("error", "Select an asset from the asset list before opening a request.");
    return;
  }
  const payload = {
    asset_id: assetId,
    title: form.title.value.trim(),
    description: form.description.value.trim() || null,
    issue_code: form.issue_code.value.trim() || null,
  };
  const response = await apiFetch("/maintenance-requests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    setNotice("error", await readError(response, "Unable to create maintenance request"));
    return;
  }
  form.reset();
  await loadWorkspace();
  setNotice("success", "Maintenance request opened.");
  render();
}

async function handleStatusUpdate(event, item) {
  event.preventDefault();
  const form = event.currentTarget;
  const nextStatus = form.status.value;
  const payload = { status: nextStatus };
  if (nextStatus === "assigned") {
    if (!form.assigned_engineer_id.value) {
      setNotice("error", "Select an engineer before assigning the request.");
      return;
    }
    payload.assigned_engineer_id = form.assigned_engineer_id.value;
    payload.internal_notes = form.internal_notes.value.trim() || null;
  }
  const response = await apiFetch(`/maintenance-requests/${item.id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    setNotice("error", await readError(response, "Unable to update request status"));
    return;
  }
  await loadWorkspace();
  setNotice("success", `Request moved to ${statusLabel(nextStatus)}.`);
  render();
}

async function handleQuickStatusUpdate(item, nextStatus) {
  const response = await apiFetch(`/maintenance-requests/${item.id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: nextStatus }),
  });
  if (!response.ok) {
    setNotice("error", await readError(response, "Unable to update request status"));
    return;
  }
  await loadWorkspace();
  setNotice("success", `Request moved to ${statusLabel(nextStatus)}.`);
  render();
}

function renderNotice() {
  clear(dom.noticePanel);
  dom.noticePanel.classList.toggle("is-empty", !state.notice);
  if (!state.notice) {
    return;
  }
  dom.noticePanel.append(
    node("div", {
      className: `notice is-${state.notice.tone}`,
      text: state.notice.text,
    })
  );
}

function renderHero() {
  clear(dom.heroPanel);
  const operationalLines = state.user
    ? [
        ["Current role", roleLabel(state.user.role)],
        ["Assets in view", String(state.assets.length)],
        ["Requests in view", String(state.requests.length)],
      ]
    : [
        ["Workflow", "asset -> request -> assign -> in progress -> completed"],
        ["Security posture", "same-origin fetch - memory-only tokens - CSP"],
        ["Privileged export", "supervisor / technical admin"],
      ];

  const heroShell = node("div", { className: "hero-shell" }, [
    node("div", { className: "hero-copy" }, [
      node("p", {
        className: "microcopy",
        text: state.user ? "Active field workspace" : "Secure static frontend",
      }),
      node("h2", {
        text: state.user
          ? `Dispatch-ready view for ${roleLabel(state.user.role)} operations.`
          : "A clean operator surface for the existing FastAPI maintenance MVP.",
      }),
      node("p", {
        text: state.user
          ? "Review the latest work orders, assign the right engineer, move requests through the status flow, and audit privileged report output from the same secure perimeter."
          : "Sign in with the seeded MVP accounts to inspect registered equipment, open maintenance requests, progress assigned work, and review summary exports without exposing unsafe rendering paths.",
      }),
    ]),
    node("div", { className: "hero-metrics" }, [
      node("span", {
        className: "pill",
        text: state.user ? "Live operational surface" : "No browser token persistence",
      }),
      node(
        "div",
        { className: "metric-strip" },
        operationalLines.map(([label, value]) =>
          node("div", { className: "metric-line" }, [
            node("span", { text: label }),
            node("strong", { text: value }),
          ])
        )
      ),
    ]),
  ]);
  dom.heroPanel.append(heroShell);
}

function renderRail() {
  clear(dom.railNav);
  const views = [
    ["overview", "Overview", "surface"],
    ["assets", "Assets", `${state.assets.length}`],
    ["requests", "Requests", `${state.requests.length}`],
  ];
  if (isPrivileged()) {
    views.push(["reports", "Summary Report", `${state.report ? state.report.items.length : 0}`]);
  }
  views.forEach(([view, label, meta]) => {
    const button = node("button", {
      className: `nav-button${state.view === view ? " is-active" : ""}`,
      type: "button",
    }, [
      node("span", { className: "nav-label", text: label }),
      node("span", { className: "nav-meta", text: meta }),
    ]);
    button.addEventListener("click", () => {
      state.view = view;
      render();
    });
    dom.railNav.append(button);
  });

  dom.sessionNote.textContent = state.user
    ? `${roleLabel(state.user.role)} session loaded. Tokens stay in memory only, so a full page reload clears the current login.`
    : "Tokens stay in memory only. Reloading the page clears the current session.";
}

function renderLogin() {
  const stage = node("section", { className: "auth-stage" });
  const loginForm = node("form");
  loginForm.append(
    node("div", { className: "field-group" }, [
      node("label", { attrs: { for: "login-email" }, text: "Email" }),
      node("input", {
        id: "login-email",
        name: "email",
        type: "email",
        placeholder: "engineer@example.com",
        attrs: { autocomplete: "username" },
      }),
    ]),
    node("div", { className: "field-group" }, [
      node("label", { attrs: { for: "login-password" }, text: "Password" }),
      node("input", {
        id: "login-password",
        name: "password",
        type: "password",
        placeholder: "Strong password",
        attrs: { autocomplete: "current-password" },
      }),
    ]),
    node("div", { className: "button-row" }, [
      node("button", { className: "primary-button", type: "submit", text: "Open workspace" }),
    ])
  );
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const email = form.email.value.trim();
    const password = form.password.value;
    try {
      await login(email, password);
      state.view = "overview";
      setNotice("success", "Secure session established.");
      render();
    } catch (error) {
      setNotice("error", error instanceof Error ? error.message : "Login failed");
    }
  });

  stage.append(
    node("div", { className: "auth-panel" }, [
      node("p", { className: "microcopy", text: "Sign in to continue" }),
      node("h3", { text: "Use the existing MVP identities" }),
      node("p", {
        text: "The frontend talks to the same FastAPI endpoints already used by the tests. No new browser-side trust assumptions are introduced.",
      }),
      loginForm,
    ]),
    node("div", { className: "detail-panel" }, [
      node("p", { className: "microcopy", text: "Operational notes" }),
      node("div", { className: "detail-list" }, [
        detailRow("Engineer", "Create requests and progress assigned work."),
        detailRow("Supervisor", "Register assets, assign engineers, review reports."),
        detailRow("Technical Admin", "Review privileged output and supervisory flows."),
        detailRow("Session handling", "Access and refresh tokens are held in page memory only."),
      ]),
    ])
  );
  return stage;
}

function detailRow(label, value) {
  return node("div", { className: "detail-row" }, [
    node("span", { text: label }),
    node("strong", { text: value }),
  ]);
}

function renderOverview() {
  const reportCounts = state.report
    ? [
        ["Total requests", String(state.report.total_requests)],
        ["Open", String(state.report.open_requests)],
        ["Completed", String(state.report.completed_requests)],
      ]
    : [
        ["Assets", String(state.assets.length)],
        ["Requests", String(state.requests.length)],
        ["Role", roleLabel(state.user.role)],
      ];

  return node("section", { className: "overview-stage" }, [
    node("div", { className: "section-header" }, [
      node("div", {}, [
        node("h3", { text: "Selected KPIs" }),
        node("p", {
          text: "Scan the operational surface first: asset register, active work orders, and privileged report counts.",
        }),
      ]),
      node("div", { className: "pill", text: "Same API perimeter" }),
    ]),
    node(
      "div",
      { className: "overview-grid" },
      reportCounts.map(([label, value]) =>
        node("div", { className: "surface-block stat-panel" }, [
          node("p", { className: "stat-label", text: label }),
          node("p", { className: "stat-value", text: value }),
        ])
      )
    ),
    node("div", { className: "stage-split" }, [
      node("div", { className: "surface-block" }, [
        node("div", { className: "split-header" }, [
          node("div", {}, [
            node("h3", { text: "Recent maintenance traffic" }),
            node("p", { text: "Latest requests visible to the signed-in role." }),
          ]),
        ]),
        requestsTable(state.requests.slice(0, 5), false),
      ]),
      node("div", { className: "surface-block" }, [
        node("div", { className: "split-header" }, [
          node("div", {}, [
            node("h3", { text: "Asset register snapshot" }),
            node("p", { text: "Newest registered equipment entries." }),
          ]),
        ]),
        assetsTable(state.assets.slice(0, 5)),
      ]),
    ]),
  ]);
}

function assetsTable(items) {
  if (!items.length) {
    return node("p", { className: "empty-state", text: "No assets are loaded into the current view." });
  }
  const table = node("table");
  table.append(
    node("thead", {}, [
      node("tr", {}, [
        node("th", { text: "Asset" }),
        node("th", { text: "Facility" }),
        node("th", { text: "Equipment" }),
        node("th", { text: "Location" }),
      ]),
    ]),
    node(
      "tbody",
      {},
      items.map((asset) =>
        node("tr", {}, [
          node("td", {}, [node("strong", { text: asset.asset_tag }), node("div", { text: asset.name })]),
          node("td", { text: asset.facility }),
          node("td", { text: asset.equipment_type }),
          node("td", { text: asset.location_detail || "Not specified" }),
        ])
      )
    )
  );
  return node("div", { className: "table-shell" }, [table]);
}

function requestsTable(items, includeActions = true) {
  if (!items.length) {
    return node("p", { className: "empty-state", text: "No maintenance requests are visible in the current view." });
  }
  const table = node("table");
  table.append(
    node("thead", {}, [
      node("tr", {}, [
        node("th", { text: "Request" }),
        node("th", { text: "Asset" }),
        node("th", { text: "Status" }),
        node("th", { text: "Assigned engineer" }),
        node("th", { text: "Action" }),
      ]),
    ])
  );
  const body = node("tbody");
  items.forEach((item) => {
    const actionCell = node("td");
    if (includeActions) {
      const transitions = allowedTransitions(item);
      if (transitions.length) {
        const actionStack = node("div", { className: "action-stack" });
        if (transitions.includes("assigned")) {
          if (state.engineers.length) {
            const form = node("form", { className: "inline-form" });
            form.append(node("input", { type: "hidden", name: "status", value: "assigned" }));
            const engineerSelect = node("select", { name: "assigned_engineer_id" });
            state.engineers.forEach((engineer) => {
              engineerSelect.append(
                node("option", {
                  value: engineer.id,
                  text: `${engineer.full_name} - ${engineer.email}`,
                })
              );
            });
            form.append(engineerSelect);
            form.append(
              node("textarea", {
                name: "internal_notes",
                rows: "3",
                placeholder: "Dispatch note for the assigned engineer",
              })
            );
            const submit = node("button", { className: "secondary-button", type: "submit", text: "Assign engineer" });
            form.append(node("div", { className: "button-row" }, [submit]));
            form.addEventListener("submit", (event) => {
              handleStatusUpdate(event, item);
            });
            actionStack.append(form);
          } else {
            actionStack.append(node("span", { className: "subtle-copy", text: "Assignment unavailable: no engineers loaded." }));
          }
        }
        transitions.filter((transition) => transition !== "assigned").forEach((transition) => {
          const button = node("button", {
            className: transition === "cancelled" ? "danger-button" : "secondary-button",
            type: "button",
            text: actionLabel(transition),
          });
          button.addEventListener("click", () => {
            handleQuickStatusUpdate(item, transition);
          });
          actionStack.append(button);
        });
        actionCell.append(actionStack);
      } else {
        actionCell.append(node("span", { className: "subtle-copy", text: "No available action for this role/state." }));
      }
    }
    body.append(
      node("tr", {}, [
        node("td", {}, [node("strong", { text: item.title }), node("div", { text: item.description || "No description" })]),
        node("td", {}, [renderAssetCell(item.asset_id)]),
        node("td", {}, [statusChip(item.status)]),
        node("td", {}, [renderEngineerCell(item.assigned_engineer_id)]),
        actionCell,
      ])
    );
  });
  table.append(body);
  return node("div", { className: "table-shell" }, [table]);
}

function assetCreateForm() {
  if (!isPrivileged()) {
    return node("p", { className: "field-hint", text: "Asset registration remains reserved for supervisor and technical admin roles." });
  }
  const form = node("form");
  form.append(
    node("div", { className: "form-grid" }, [
      field("Asset tag", node("input", { name: "asset_tag", placeholder: "PUMP-4012" })),
      field("Asset name", node("input", { name: "name", placeholder: "Transfer Pump" })),
      field("Facility", node("input", { name: "facility", placeholder: "South Compression Yard" })),
      field("Equipment type", node("input", { name: "equipment_type", placeholder: "Pump" })),
    ]),
    field("Location detail", node("textarea", { name: "location_detail", rows: "4", placeholder: "Bay 4 / Skid 2" })),
    node("div", { className: "button-row" }, [
      node("button", { className: "primary-button", type: "submit", text: "Register asset" }),
    ])
  );
  form.addEventListener("submit", handleAssetCreate);
  return form;
}

function assetChooser() {
  const listId = "asset-choice-options";
  const assetIdInput = node("input", { type: "hidden", name: "asset_id" });
  const searchInput = node("input", {
    name: "asset_search",
    placeholder: "Search by asset tag, name, facility, or equipment type",
    attrs: { list: listId, autocomplete: "off", required: "required" },
  });
  const options = node("datalist", { id: listId });
  const labelToId = new Map();
  state.assets.forEach((asset) => {
    const label = assetSearchLabel(asset);
    labelToId.set(label, asset.id);
    options.append(node("option", { value: label }));
  });
  searchInput.addEventListener("input", () => {
    assetIdInput.value = labelToId.get(searchInput.value) || "";
  });
  return node("div", {}, [field("Asset", searchInput), assetIdInput, options]);
}

function requestCreateForm() {
  if (!state.assets.length) {
    return node("div", { className: "empty-state" }, [
      node("p", { text: "No assets are available for new maintenance requests." }),
      node("button", {
        className: "secondary-button",
        type: "button",
        text: "Open request disabled",
        attrs: { disabled: "disabled" },
      }),
    ]);
  }
  const form = node("form");
  form.append(
    assetChooser(),
    node("div", { className: "form-grid" }, [
      field("Title", node("input", { name: "title", placeholder: "Seal leakage inspection" })),
      field("Issue code", node("input", { name: "issue_code", placeholder: "LEAK-01" })),
    ]),
    field("Description", node("textarea", { name: "description", rows: "5", placeholder: "Describe the observed fault, symptoms, and current operating state." })),
    node("div", { className: "button-row" }, [
      node("button", { className: "primary-button", type: "submit", text: "Open request" }),
    ])
  );
  form.addEventListener("submit", handleRequestCreate);
  return form;
}

function field(labelText, control) {
  return node("div", { className: "field-group" }, [
    node("label", { text: labelText }),
    control,
  ]);
}

function renderAssetsView() {
  return node("section", { className: "stage" }, [
    node("div", { className: "stage-split" }, [
      node("div", { className: "surface-block" }, [
        node("div", { className: "split-header" }, [
          node("div", {}, [
            node("h3", { text: "Registered assets" }),
            node("p", { text: "The current API view is bounded and sorted by the latest registration timestamp." }),
          ]),
          node("div", { className: "pill", text: `${state.assets.length} loaded` }),
        ]),
        assetsTable(state.assets),
      ]),
      node("div", { className: "surface-block" }, [
        node("div", { className: "split-header" }, [
          node("div", {}, [
            node("h3", { text: "Register a new asset" }),
            node("p", { text: "Supervisor and technical admin users can stage the next work order target here." }),
          ]),
        ]),
        assetCreateForm(),
      ]),
    ]),
  ]);
}

function renderRequestsView() {
  return node("section", { className: "stage" }, [
    node("div", { className: "stage-split" }, [
      node("div", { className: "surface-block" }, [
        node("div", { className: "split-header" }, [
          node("div", {}, [
            node("h3", { text: "Maintenance requests" }),
            node("p", { text: "Role-aware actions stay in the backend; the UI only exposes transitions the current surface can justify." }),
          ]),
          node("div", { className: "pill", text: `${state.requests.length} loaded` }),
        ]),
        requestsTable(state.requests),
      ]),
      node("div", { className: "surface-block" }, [
        node("div", { className: "split-header" }, [
          node("div", {}, [
            node("h3", { text: "Open a new request" }),
            node("p", { text: "Use the existing backend validation and workflow states. No browser-side markup insertion is used." }),
          ]),
        ]),
        requestCreateForm(),
      ]),
    ]),
  ]);
}

function renderReportView() {
  if (!isPrivileged() || !state.report) {
    return node("section", { className: "stage" }, [
      node("div", { className: "surface-block" }, [
        node("h3", { text: "Summary report" }),
        node("p", { text: "This surface is only available to supervisor and technical admin roles." }),
      ]),
    ]);
  }
  const refreshButton = node("button", {
    className: "ghost-button",
    type: "button",
    text: "Refresh",
  });
  refreshButton.addEventListener("click", async () => {
    try {
      await loadWorkspace();
      setNotice("success", "Summary report refreshed.");
      render();
    } catch (error) {
      setNotice("error", error instanceof Error ? error.message : "Unable to refresh report");
    }
  });
  return node("section", { className: "stage" }, [
    node("div", { className: "surface-block" }, [
      node("div", { className: "section-header" }, [
        node("div", {}, [
          node("h3", { text: "Privileged maintenance summary" }),
          node("p", { text: "The list is bounded on the server side while totals still reflect the full dataset." }),
        ]),
        refreshButton,
      ]),
      node("div", { className: "overview-grid" }, [
        statPanel("Total requests", String(state.report.total_requests)),
        statPanel("Open", String(state.report.open_requests)),
        statPanel("Completed", String(state.report.completed_requests)),
      ]),
      node("div", { className: "surface-block" }, [reportTable(state.report.items)]),
    ]),
  ]);
}

function statPanel(label, value) {
  return node("div", { className: "surface-block stat-panel" }, [
    node("p", { className: "stat-label", text: label }),
    node("p", { className: "stat-value", text: value }),
  ]);
}

function reportTable(items) {
  if (!items.length) {
    return node("p", { className: "empty-state", text: "No report rows are available." });
  }
  const table = node("table");
  table.append(
    node("thead", {}, [
      node("tr", {}, [
        node("th", { text: "Asset" }),
        node("th", { text: "Request title" }),
        node("th", { text: "Status" }),
        node("th", { text: "Assigned engineer" }),
      ]),
    ]),
    node(
      "tbody",
      {},
      items.map((item) =>
        node("tr", {}, [
          node("td", { text: item.asset_tag }),
          node("td", { text: item.title }),
          node("td", {}, [statusChip(item.status)]),
          node("td", {}, [renderEngineerCell(item.assigned_engineer_id)]),
        ])
      )
    )
  );
  return node("div", { className: "table-shell" }, [table]);
}

function renderWorkspace() {
  if (!state.user) {
    return renderLogin();
  }
  if (state.view === "assets") {
    return renderAssetsView();
  }
  if (state.view === "requests") {
    return renderRequestsView();
  }
  if (state.view === "reports") {
    return renderReportView();
  }
  return renderOverview();
}

function render() {
  renderHero();
  renderRail();
  renderNotice();
  clear(dom.workspaceRoot);

  if (state.user) {
    const toolbar = node("section", { className: "stage" }, [
      node("div", { className: "section-header" }, [
        node("div", {}, [
          node("h3", { text: `${state.user.full_name}` }),
          node("p", { text: `${roleLabel(state.user.role)} - ${state.user.email}` }),
        ]),
        node("div", { className: "button-row" }, [
          node("button", { className: "ghost-button", type: "button", text: "Sign out" }),
        ]),
      ]),
    ]);
    toolbar.querySelector("button").addEventListener("click", logout);
    dom.workspaceRoot.append(toolbar);
  }

  dom.workspaceRoot.append(renderWorkspace());
}

async function bootstrap() {
  render();
}

bootstrap();
