/** @odoo-module **/

document.addEventListener("DOMContentLoaded", function () {
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
});
