/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.MyFatoorahApplePay = publicWidget.Widget.extend({
    selector: '.oe_website_sale',

    start: function () {
        this.insertApplePayButton();
        return this._super.apply(this, arguments);
    },

    insertApplePayButton: function () {
        // Prevent duplicate button insertion
        if (document.getElementById('mf_apple_pay_wrapper')) {
            return;
        }

        const $payNowBtn = this.$('button[name="o_payment_submit_button"]');

        // PAY NOW button may not be rendered yet — retry after 500ms
        if (!$payNowBtn.length) {
            setTimeout(() => this.insertApplePayButton(), 500);
            return;
        }

        const html = `
            <div id="mf_apple_pay_wrapper" class="mb-3 mt-2">
                <button type="button"
                        id="mf_apple_pay_btn"
                        class="btn btn-dark w-100 d-flex align-items-center justify-content-center"
                        style="min-height:48px; border-radius:6px; background-color:#000 !important; color:#fff !important; font-weight:bold; border:none;">
                    <span style="font-size:22px; line-height:1;"></span>
                    <span class="ms-2">Pay with Apple Pay</span>
                </button>
                <div class="text-center my-2 text-muted small">—— OR ——</div>
            </div>
        `;

        $payNowBtn.before(html);
        this.$('#mf_apple_pay_btn').on('click', this._onApplePayClick.bind(this));
    },

    _onApplePayClick: async function (ev) {
    ev.preventDefault();
    ev.stopPropagation(); // ADD THIS — prevents Odoo form submission

    const $btn = $(ev.currentTarget);
    const originalHtml = $btn.html();

    // Also disable the main PAY NOW button to prevent double submission
    $('button[name="o_payment_submit_button"]').prop('disabled', true);

    $btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span>');

    try {
        const response = await fetch('/payment/myfatoorah/applepay/pay', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }),
        });

        const data = await response.json();
        const result = data.result;

        if (result && result.success) {
            // Redirect to MyFatoorah Apple Pay page
            window.location.href = result.redirect_url;
        } else {
            throw new Error(result ? result.message : 'MyFatoorah: Failed to generate link.');
        }

    } catch (error) {
        console.error('Apple Pay Error:', error);
        alert(error.message || 'An error occurred.');
        // Re-enable both buttons on failure
        $btn.prop('disabled', false).html(originalHtml);
        $('button[name="o_payment_submit_button"]').prop('disabled', false);
    }
}
});