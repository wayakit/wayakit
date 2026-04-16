/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.MyFatoorahApplePayButton = publicWidget.Widget.extend({
    selector: "#mf_apple_pay_btn",

    events: {
        click: "_onClickApplePay",
    },

    start() {
        const wrapper = document.getElementById("mf_apple_pay_wrapper");

        if (!(window.ApplePaySession && window.ApplePaySession.canMakePayments())) {
            if (wrapper) {
                wrapper.classList.add("d-none");
            }
            return Promise.resolve();
        }

        return this._super(...arguments);
    },

    async _onClickApplePay(ev) {
        ev.preventDefault();

        const btn = ev.currentTarget;
        const originalHtml = btn.innerHTML;

        btn.disabled = true;
        btn.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2"></span>
            <span>Redirecting to Apple Pay...</span>
        `;

        try {
            const result = await jsonrpc('/payment/myfatoorah/applepay/pay', {});

            if (!result || !result.success) {
                throw new Error((result && result.message) || "Unable to start Apple Pay.");
            }

            window.location.href = result.redirect_url;
        } catch (error) {
            console.error("Apple Pay error:", error);
            alert(error.message || "Unable to start Apple Pay.");
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    },
});