// shared namespace for page scripts
window.CW = {
  palette: [
    "#2446e8",
    "#ef4a2b",
    "#f5a623",
    "#12a67a",
    "#7a5af8",
    "#0ea5c6",
    "#e8651a",
    "#5f7aa8",
  ],
};

// animate numbers from their last shown value to the target
CW.count = (el, target) => {
  const from = Number(el.dataset.shown || 0),
    start = performance.now(),
    span = 800,
    tail = el.dataset.suffix || "";
  if (from === target) {
    el.textContent = target.toLocaleString() + tail;
    return;
  }
  const tick = (now) => {
    const t = Math.min((now - start) / span, 1),
      eased = 1 - Math.pow(1 - t, 3);
    el.textContent =
      Math.round(from + (target - from) * eased).toLocaleString() + tail;
    if (t < 1) requestAnimationFrame(tick);
    else el.dataset.shown = target;
  };
  requestAnimationFrame(tick);
};

// small toast helper used by scripts and flash messages
CW.toast = (message, category = "info") => {
  const box = document.getElementById("toasts");
  const icon =
    {
      success: "check-circle-fill",
      danger: "exclamation-octagon-fill",
      info: "info-circle-fill",
    }[category] || "info-circle-fill";
  const toast = document.createElement("div");
  toast.className = "toast-x " + category;
  toast.setAttribute("role", category === "danger" ? "alert" : "status");
  toast.innerHTML = '<i class="bi bi-' + icon + '"></i><span></span>';
  toast.querySelector("span").textContent = message;
  box.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("out");
    setTimeout(() => toast.remove(), 300);
  }, 5000);
};

document.addEventListener("DOMContentLoaded", () => {
  // mobile sidebar with backdrop
  const side = document.getElementById("side");
  const closeNav = () => {
    side?.classList.remove("open");
    document.body.classList.remove("nav-open");
  };
  document.getElementById("menu-btn")?.addEventListener("click", () => {
    side.classList.toggle("open");
    document.body.classList.toggle("nav-open");
  });
  document.querySelector(".backdrop")?.addEventListener("click", closeNav);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeNav();
    if (
      e.key === "/" &&
      !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)
    ) {
      const s = document.getElementById("global-search");
      if (s) {
        e.preventDefault();
        s.focus();
      }
    }
  });

  // flash messages become toasts
  document
    .querySelectorAll("[data-flash]")
    .forEach((item) => CW.toast(item.textContent, item.dataset.cat));

  // confirm destructive forms
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // loading state on submit buttons to prevent double posts
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (e.defaultPrevented || !form.checkValidity()) return;
      const button = e.submitter || form.querySelector("button.btn-x");
      if (!button) return;
      setTimeout(() => {
        button.classList.add("is-loading");
        button.disabled = true;
      }, 0);
      form.querySelector(".progress")?.classList.add("on");
      if (form.hasAttribute("data-download"))
        setTimeout(() => {
          button.classList.remove("is-loading");
          button.disabled = false;
        }, 3000);
    });
  });
  window.addEventListener("pageshow", () =>
    document.querySelectorAll(".is-loading").forEach((b) => {
      b.classList.remove("is-loading");
      b.disabled = false;
    }),
  );

  // drag and drop upload area
  const drop = document.querySelector(".drop");
  if (drop) {
    const input = drop.querySelector("input"),
      label = drop.querySelector("[data-file]"),
      size = drop.querySelector("[data-size]");
    ["dragenter", "dragover"].forEach((n) =>
      drop.addEventListener(n, (e) => {
        e.preventDefault();
        drop.classList.add("over");
      }),
    );
    ["dragleave", "drop"].forEach((n) =>
      drop.addEventListener(n, (e) => {
        e.preventDefault();
        drop.classList.remove("over");
      }),
    );
    drop.addEventListener("drop", (e) => {
      input.files = e.dataTransfer.files;
      input.dispatchEvent(new Event("change"));
    });
    input.addEventListener("change", () => {
      const file = input.files[0];
      drop.classList.toggle("has", !!file);
      label.textContent = file ? file.name : "Drop a log file here or browse";
      size.textContent = file
        ? (file.size / 1024 < 1024
            ? (file.size / 1024).toFixed(1) + " KB"
            : (file.size / 1048576).toFixed(2) + " MB") + " ready to analyse"
        : size.dataset.default;
    });
  }

  // click to copy
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    e.stopPropagation();
    navigator.clipboard?.writeText(btn.dataset.copy).then(() => {
      btn.classList.add("done");
      const icon = btn.querySelector("i");
      const old = icon.className;
      icon.className = "bi bi-check2";
      setTimeout(() => {
        btn.classList.remove("done");
        icon.className = old;
      }, 1400);
    });
  });

  // whole table rows open their detail page
  document.querySelectorAll("tr[data-href]").forEach((row) =>
    row.addEventListener("click", (e) => {
      if (e.target.closest("a,button,form,input,select")) return;
      window.location.href = row.dataset.href;
    }),
  );

  // show or hide passwords and warn about caps lock
  document.querySelectorAll(".pw button").forEach((btn) =>
    btn.addEventListener("click", () => {
      const input = btn.parentElement.querySelector("input"),
        show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.querySelector("i").className =
        "bi bi-" + (show ? "eye-slash" : "eye");
    }),
  );
  document.querySelectorAll("input[type=password]").forEach((input) =>
    input.addEventListener("keyup", (e) => {
      const hint = document.querySelector(".caps");
      if (hint && e.getModifierState)
        hint.style.display = e.getModifierState("CapsLock") ? "block" : "none";
    }),
  );

  // quick status buttons on an alert
  document.querySelectorAll("[data-quick-status]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const select = document.getElementById("status"),
        note = document.getElementById("note");
      select.value = btn.dataset.quickStatus;
      select.dispatchEvent(new Event("change"));
      note.focus();
      note.scrollIntoView({ behavior: "smooth", block: "center" });
    }),
  );

  // number counters on static pages
  document
    .querySelectorAll("[data-count]")
    .forEach((el) => CW.count(el, Number(el.dataset.count)));
});
