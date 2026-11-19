$(function () {
  // Section order and rendering: "text" -> paragraph, "list" -> bullets, "angles" -> named ideas with a hook.
  // "major" sections are the two extra outputs the brand asked for, shown as their own parts.
  var SECTIONS = [
    ["overview", "Overview", "text"],
    ["objective", "Objective", "text"],
    ["target_audience", "Target audience", "text"],
    ["key_messages", "Key messages", "list"],
    ["deliverables", "Deliverables", "list"],
    ["dos", "Do's", "list"],
    ["donts", "Don'ts", "list"],
    ["usage_rights", "Usage rights", "text"],
    ["content_angles", "Content angles", "angles", true],
    ["creator_criteria", "Creator selection criteria", "list", true]
  ];
  var TBD_RE = /\[TBD:[^\]]*\]/g;

  var $form = $("#brief-form");
  var $btn = $("#generate-btn");
  var csrf = $form.find("[name=csrfmiddlewaretoken]").val();
  var runId = null, edited = false;  // current brief, for the copy-rate metric

  function escapeHtml(s) { return $("<div>").text(s).html(); }
  function withTbd(s) { return escapeHtml(s).replace(TBD_RE, function (m) { return '<span class="tbd">' + m + "</span>"; }); }

  function show(state) {
    $("#brief-empty").prop("hidden", state !== "empty");
    $("#brief-loading").prop("hidden", state !== "loading");
    $("#brief").prop("hidden", state !== "brief");
  }

  function clearErrors() {
    $("#form-error").prop("hidden", true).text("");
    $form.find(".field").removeClass("has-error").find(".field-error").remove();
  }

  function showErrors(message, fields) {
    $("#form-error").text(message).prop("hidden", false);
    $.each(fields || {}, function (name, msg) {
      $form.find("[name=" + name + "]").closest(".field").addClass("has-error")
        .append($('<span class="field-error">').text(msg));
    });
  }

  function updateTbdCount() {
    var n = ($("#brief").text().match(TBD_RE) || []).length;
    $("#tbd-count").toggleClass("has-tbd", n > 0)
      .text(n ? n + (n === 1 ? " detail" : " details") + " to fill in before sending" : "Ready to send");
  }

  function renderBrief(brief) {
    $("#brief-title").html(withTbd(brief.title));
    var $sections = $("#brief-sections").empty();
    $.each(SECTIONS, function (_, s) {
      var key = s[0], label = s[1], kind = s[2], major = s[3], value = brief[key];
      var $body;
      if (kind === "angles") {
        $body = $("<ul>");
        $.each(value || [], function (_, a) {
          $body.append($("<li>").append(
            $('<span class="angle-name">').html(withTbd(a.name)), document.createTextNode(": "),
            $("<span>").html(withTbd(a.idea)),
            $('<span class="angle-hook">').html("Hook: \u201c" + withTbd(a.hook) + "\u201d")
          ));
        });
      } else if (kind === "list") {
        $body = $("<ul>");
        $.each(value || [], function (_, item) { $body.append($("<li>").html(withTbd(item))); });
      } else {
        $body = $("<p>").html(withTbd(value || ""));
      }
      // Copy brief reads labels from data-label, so editing a heading can't break it.
      $sections.append($('<section class="brief-section">').toggleClass("major", !!major)
        .attr("data-key", key).attr("data-label", label)
        .append($("<h3>").text(label), $body));
    });
    updateTbdCount();
  }

  function briefAsText() {
    var out = [$.trim($("#brief-title").text()), ""];
    $("#brief-sections .brief-section").each(function () {
      var $s = $(this), $list = $s.find("ul");
      out.push($s.data("label").toUpperCase());
      if ($list.length) {
        $list.find("li").each(function () {
          var $li = $(this), $hook = $li.find(".angle-hook");
          var main = $.trim($li.clone().find(".angle-hook").remove().end().text());
          if (main) out.push("- " + main);
          if ($hook.length && $.trim($hook.text())) out.push("  " + $.trim($hook.text()));
        });
      } else {
        out.push($.trim($s.find("p").text()));
      }
      out.push("");
    });
    return out.join("\n").trim() + "\n";
  }

  $form.on("submit", function (e) {
    e.preventDefault();
    clearErrors();
    var payload = {};
    $.each($form.serializeArray(), function (_, f) { if (f.name !== "csrfmiddlewaretoken") payload[f.name] = f.value; });

    $btn.prop("disabled", true).text("Generating…");
    show("loading");

    $.ajax({
      url: "/api/briefs/", method: "POST", contentType: "application/json",
      headers: { "X-CSRFToken": csrf }, data: JSON.stringify(payload), timeout: 120000
    }).done(function (res) {
      runId = res.id; edited = false;
      renderBrief(res.brief);
      show("brief");
    }).fail(function (xhr) {
      var body = xhr.responseJSON || {};
      showErrors(body.error || "Something went wrong. Try again.", body.fields);
      show($("#brief-sections").children().length ? "brief" : "empty");
    }).always(function () {
      $btn.prop("disabled", false).text("Generate brief");
    });
  });

  $("#brief-doc").on("input", function () { edited = true; updateTbdCount(); });

  // In one editing host a triple-click also grabs the line break after the block, so typing would
  // swallow the next section's heading. Keep triple-click selection inside the clicked block.
  $("#brief-doc").on("mouseup", function (e) {
    if (e.originalEvent.detail < 3) return;
    var block = $(e.target).closest("p, li, h2, h3")[0];
    if (!block) return;
    var range = document.createRange();
    range.selectNodeContents(block);
    var sel = window.getSelection();
    sel.removeAllRanges(); sel.addRange(range);
  });

  // Fire-and-forget: measurement must never get in the way of copying.
  function trackCopy() {
    if (!runId) return;
    $.ajax({
      url: "/api/briefs/" + runId + "/copied/", method: "POST", contentType: "application/json",
      headers: { "X-CSRFToken": csrf },
      data: JSON.stringify({ edited: edited, tbd_remaining: ($("#brief-doc").text().match(TBD_RE) || []).length })
    });
  }

  // Theme: follows the OS until the user picks one; the choice is saved per browser.
  var root = document.documentElement;
  var systemDark = window.matchMedia("(prefers-color-scheme: dark)");
  function isDark() {
    var t = root.getAttribute("data-theme");
    return t ? t === "dark" : systemDark.matches;
  }
  function syncThemeUI() {
    var dark = isDark();
    $(root).toggleClass("is-dark", dark);
    $("#theme-toggle").attr("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  }
  $("#theme-toggle").on("click", function () {
    var next = isDark() ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
    syncThemeUI();
  });
  if (systemDark.addEventListener) systemDark.addEventListener("change", syncThemeUI);
  syncThemeUI();

  $("#copy-btn").on("click", function () {
    var $b = $(this), text = briefAsText();
    function done() { trackCopy(); $b.addClass("copied").text("Copied!"); setTimeout(function () { $b.removeClass("copied").text("Copy brief"); }, 1800); }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done);
    } else {
      var $t = $("<textarea>").val(text).css({ position: "fixed", opacity: 0 }).appendTo("body");
      $t[0].select(); document.execCommand("copy"); $t.remove(); done();
    }
  });
});
