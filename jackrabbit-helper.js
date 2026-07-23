
(function () {
  function showFallback(tableId, portalUrl) {
    var table = document.getElementById(tableId);
    if (!table) return;
    setTimeout(function () {
      var rows = table.querySelectorAll("tbody tr");
      if (!rows.length) {
        var fallback = document.createElement("p");
        fallback.className = "jackrabbit-fallback";
        fallback.innerHTML = 'If class openings do not load, <a style="color:#24c8d8;font-weight:900" href="' + portalUrl + '" target="_blank" rel="noopener">open registration in the Parent Portal</a>.';
        table.closest(".jackrabbit-frame").appendChild(fallback);
      }
    }, 3500);
  }
  window.StageStarzJackrabbit = { showFallback: showFallback };
})();
