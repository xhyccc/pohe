/* POHE field guide — progressive enhancement only.
   Filtering, deep links, and the small-screen navigation.
   No network requests: everything is already in the document. */

(function () {
  "use strict";

  var PARAM_KEYS = ["q", "family", "activity", "hypothesis", "evidence"];

  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function normalise(value) {
    return String(value || "").toLowerCase().trim();
  }

  function splitTokens(value) {
    return String(value || "")
      .split(/\s+/)
      .filter(Boolean);
  }

  function setupNavigation() {
    var toggle = document.getElementById("nav-toggle");
    var nav = document.getElementById("site-nav");
    if (!toggle || !nav) {
      return;
    }
    function setOpen(open) {
      toggle.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);
    }
    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) {
        setOpen(false);
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        toggle.focus();
      }
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth > 780) {
        setOpen(false);
      }
    });
  }

  function setupCatalog() {
    var search = document.getElementById("pattern-search");
    var family = document.getElementById("family-filter");
    var activity = document.getElementById("activity-filter");
    var hypothesis = document.getElementById("hypothesis-filter");
    var evidence = document.getElementById("evidence-filter");
    var reset = document.getElementById("reset-filters");
    var results = document.getElementById("result-count");
    var empty = document.getElementById("empty-state");
    var index = document.getElementById("pattern-index");
    if (!search || !family || !activity || !hypothesis || !evidence || !index) {
      return;
    }

    var rows = Array.prototype.slice.call(index.querySelectorAll("[data-pattern]"));

    function readUrl() {
      var params = new URLSearchParams(window.location.search);
      PARAM_KEYS.forEach(function (key) {
        var value = params.get(key);
        if (value === null) {
          return;
        }
        if (key === "q") {
          search.value = value;
        } else if (key === "family") {
          family.value = value;
        } else if (key === "activity") {
          activity.value = value;
        } else if (key === "hypothesis") {
          hypothesis.value = value;
        } else if (key === "evidence") {
          evidence.value = value;
        }
      });
    }

    function writeUrl() {
      var params = new URLSearchParams();
      if (search.value.trim()) {
        params.set("q", search.value.trim());
      }
      if (family.value !== "all") {
        params.set("family", family.value);
      }
      if (activity.value !== "all") {
        params.set("activity", activity.value);
      }
      if (hypothesis.value !== "all") {
        params.set("hypothesis", hypothesis.value);
      }
      if (evidence.value !== "all") {
        params.set("evidence", evidence.value);
      }
      var query = params.toString();
      var hash = window.location.hash;
      var next = window.location.pathname + (query ? "?" + query : "") + hash;
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", next);
      }
    }

    function matches(row, term) {
      if (!term) {
        return true;
      }
      var haystack = normalise(row.getAttribute("data-search") || row.textContent);
      return term
        .split(/\s+/)
        .filter(Boolean)
        .every(function (word) {
          return haystack.indexOf(word) !== -1;
        });
    }

    function apply(persist) {
      var term = normalise(search.value);
      var familyValue = family.value;
      var activityValue = activity.value;
      var hypothesisValue = hypothesis.value;
      var evidenceValue = evidence.value;
      var visible = 0;

      rows.forEach(function (row) {
        var rowFamilies = splitTokens(row.getAttribute("data-family"));
        var rowActivities = splitTokens(row.getAttribute("data-activities"));
        var rowHypotheses = splitTokens(row.getAttribute("data-hypotheses"));
        var rowEvidence = splitTokens(row.getAttribute("data-evidence"));
        var show =
          matches(row, term) &&
          (familyValue === "all" || rowFamilies.indexOf(familyValue) !== -1) &&
          (activityValue === "all" || rowActivities.indexOf(activityValue) !== -1) &&
          (hypothesisValue === "all" || rowHypotheses.indexOf(hypothesisValue) !== -1) &&
          (evidenceValue === "all" || rowEvidence.indexOf(evidenceValue) !== -1);
        row.hidden = !show;
        if (show) {
          visible += 1;
        }
      });

      if (results) {
        results.textContent = String(visible);
      }
      if (empty) {
        empty.hidden = visible !== 0;
      }
      index.hidden = visible === 0;
      if (persist !== false) {
        writeUrl();
      }
    }

    [search, family, activity, hypothesis, evidence].forEach(function (control) {
      control.addEventListener("input", apply);
      control.addEventListener("change", apply);
    });

    function clear() {
      search.value = "";
      family.value = "all";
      activity.value = "all";
      hypothesis.value = "all";
      evidence.value = "all";
      apply();
    }

    if (reset) {
      reset.addEventListener("click", clear);
    }
    if (empty) {
      empty.addEventListener("click", function (event) {
        if (event.target.closest("[data-reset-filters]")) {
          clear();
          search.focus();
        }
      });
    }

    document.querySelectorAll("[data-family-link]").forEach(function (link) {
      link.addEventListener("click", function () {
        family.value = link.getAttribute("data-family-link") || "all";
        apply();
        if (search) {
          search.focus({ preventScroll: true });
        }
      });
    });

    document.querySelectorAll("[data-hypothesis-link]").forEach(function (link) {
      link.addEventListener("click", function () {
        hypothesis.value = link.getAttribute("data-hypothesis-link") || "all";
        apply();
        var catalog = document.getElementById("catalog");
        if (catalog && catalog.scrollIntoView) {
          catalog.scrollIntoView({ behavior: "smooth" });
        }
      });
    });

    readUrl();
    apply(false);
  }


  function setupCopyButtons() {
    var buttons = document.querySelectorAll("[data-copy]");
    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener("click", function () {
        var target = document.getElementById(button.getAttribute("data-copy") || "");
        if (!target) {
          return;
        }
        var text = target.textContent;
        var done = function () {
          var original = button.textContent;
          button.textContent = "Copied";
          window.setTimeout(function () {
            button.textContent = original;
          }, 1400);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () {});
        }
      });
    });
  }

  ready(function () {
    setupNavigation();
    setupCatalog();
    setupCopyButtons();
  });
})();
