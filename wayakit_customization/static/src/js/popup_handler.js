/** @odoo-module **/

document.addEventListener("DOMContentLoaded", function () {

    // Abrir popup al hacer click en imagen
    document.querySelectorAll('a[href="#sPopup1780331031885"], a[href="#sPopup1780329941033"]').forEach(function (link) {
        link.addEventListener("click", function (e) {
            e.preventDefault();
            var targetId = this.getAttribute("href").replace("#", "");
            var el = document.getElementById(targetId);
            if (el) {
                el.classList.remove("d-none", "o_snippet_invisible");
                el.classList.add("d-block");
                var modal = el.querySelector(".modal");
                if (modal) {
                    modal.style.display = "block";
                    modal.classList.add("show");
                }
            }
        });
    });

    // Cerrar popup - busca el s_popup visible (d-block)
    document.addEventListener("click", function (e) {
        if (e.target.closest(".s_popup_close") || e.target.closest(".js_close_popup")) {
            e.preventDefault();
            e.stopPropagation();
            // Buscar el popup que está abierto (d-block)
            var popup = document.querySelector(".s_popup.d-block");
            if (popup) {
                var modal = popup.querySelector(".modal");
                if (modal) {
                    modal.style.display = "none";
                    modal.classList.remove("show");
                }
                popup.classList.add("d-none", "o_snippet_invisible");
                popup.classList.remove("d-block");
            }
        }
    });

});