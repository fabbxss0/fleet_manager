/* FLEET MANAGER — comportements d'interface (le contrôle réel reste côté serveur). */
document.addEventListener("DOMContentLoaded", () => {
  // Menu latéral sur mobile / tablette
  document.querySelectorAll("[data-toggle-sidebar]").forEach((btn) =>
    btn.addEventListener("click", () => document.body.classList.toggle("sidebar-open"))
  );

  // Filtrage instantané : les formulaires .js-autofilter se soumettent automatiquement
  document.querySelectorAll("form.js-autofilter").forEach((form) => {
    let timer;
    form.querySelectorAll("select, input[type=date]").forEach((el) =>
      el.addEventListener("change", () => form.requestSubmit())
    );
    form.querySelectorAll("input[type=search]").forEach((el) =>
      el.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => form.requestSubmit(), 450);
      })
    );
    // Remet le curseur à la fin du champ de recherche après rechargement
    const search = form.querySelector("input[type=search]");
    if (search && search.value && search.dataset.autofocus !== undefined) {
      search.focus();
      search.setSelectionRange(search.value.length, search.value.length);
    }
  });

  // Fenêtre de confirmation de suppression (une seule modale réutilisée)
  const modalEl = document.getElementById("confirmModal");
  if (modalEl) {
    const modal = new bootstrap.Modal(modalEl);
    document.querySelectorAll("[data-confirm-url]").forEach((btn) =>
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        modalEl.querySelector("form").action = btn.dataset.confirmUrl;
        modalEl.querySelector("[data-confirm-title]").textContent = btn.dataset.confirmTitle || "Confirmer";
        modalEl.querySelector("[data-confirm-text]").textContent = btn.dataset.confirmText || "Cette action est irréversible.";
        const submit = modalEl.querySelector("[data-confirm-submit]");
        submit.textContent = btn.dataset.confirmButton || "Supprimer";
        submit.className = "btn " + (btn.dataset.confirmClass || "btn-danger");
        modal.show();
      })
    );
  }

  // Pré-remplissage du kilométrage de départ selon le véhicule choisi
  const mileageData = document.getElementById("vehicle-mileages");
  if (mileageData) {
    const mileages = JSON.parse(mileageData.textContent);
    const select = document.querySelector("[data-mileage-source]");
    const target = document.getElementById("id_start_mileage");
    const sync = () => { if (select.value && mileages[select.value] !== undefined) target.value = mileages[select.value]; };
    select.addEventListener("change", sync);
    if (!target.value) sync();
  }

  // Validation HTML5 avant envoi (confort ; la validation réelle est faite par Django)
  document.querySelectorAll("form.needs-validation").forEach((form) =>
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) { event.preventDefault(); event.stopPropagation(); }
      form.classList.add("was-validated");
    })
  );

  // Les messages de succès disparaissent après quelques secondes
  document.querySelectorAll(".messages-stack .alert-success").forEach((el) =>
    setTimeout(() => bootstrap.Alert.getOrCreateInstance(el).close(), 5000)
  );
});
