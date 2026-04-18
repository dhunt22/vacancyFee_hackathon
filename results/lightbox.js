// Lightweight image lightbox — applied to .figure--zoom > img
(function () {
  const overlay = document.getElementById("lightbox");
  const img = document.getElementById("lightboxImg");
  const closeBtn = overlay && overlay.querySelector(".lightbox__close");
  if (!overlay || !img) return;

  const open = (src, alt) => {
    img.src = src;
    img.alt = alt || "";
    overlay.hidden = false;
    document.body.style.overflow = "hidden";
  };
  const close = () => {
    overlay.hidden = true;
    img.src = "";
    document.body.style.overflow = "";
  };

  document.querySelectorAll(".figure--zoom img").forEach((el) => {
    el.style.cursor = "zoom-in";
    el.addEventListener("click", () => open(el.src, el.alt));
  });

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay || e.target === closeBtn) close();
  });
  document.addEventListener("keydown", (e) => {
    if (!overlay.hidden && e.key === "Escape") close();
  });
})();
