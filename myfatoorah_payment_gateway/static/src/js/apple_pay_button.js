/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.MyFatoorahApplePay = publicWidget.Widget.extend({
    selector: '.oe_website_sale',
    // Delegated click handler: works even after the button is re-inserted.
    events: {
        'click #mf_apple_pay_btn': '_onApplePayClick',
    },

    start: function () {
        this._ensureButton = this._ensureButton.bind(this);

        // First insertion attempt.
        this._ensureButton();

        // Odoo re-renders the checkout/payment area asynchronously (delivery
        // carrier update, payment form expansion, totals refresh...). Any of
        // those can remove our button. Watch the container and re-insert it
        // whenever it goes missing so it stays put.
        this._observer = new MutationObserver(() => {
            // Coalesce bursts of mutations into a single check per frame.
            window.requestAnimationFrame(this._ensureButton);
        });
        this._observer.observe(this.el, { childList: true, subtree: true });

        return this._super.apply(this, arguments);
    },

    destroy: function () {
        if (this._observer) {
            this._observer.disconnect();
            this._observer = null;
        }
        this._super.apply(this, arguments);
    },

    _buttonHtml: function () {
        return `
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
    },

    /**
     * Idempotent: ensures exactly one Apple Pay wrapper sits right before the
     * "Pay Now" button. Safe to call repeatedly — it only touches the DOM when
     * something is actually out of place, so it never loops with the observer.
     */
    _ensureButton: function () {
        const payNowBtn = this.el.querySelector('button[name="o_payment_submit_button"]');
        if (!payNowBtn) {
            // Pay Now button not rendered (yet, or not on this page). The
            // observer will call us again once it appears.
            return;
        }

        const existing = document.getElementById('mf_apple_pay_wrapper');
        if (existing) {
            // Already present — just make sure it's still directly above the
            // (possibly re-rendered) Pay Now button.
            if (payNowBtn.previousElementSibling !== existing) {
                payNowBtn.parentNode.insertBefore(existing, payNowBtn);
            }
            return;
        }

        payNowBtn.insertAdjacentHTML('beforebegin', this._buttonHtml());
    },

    _onApplePayClick: async function (ev) {
        ev.preventDefault();
        ev.stopPropagation();

        const $btn = $(ev.currentTarget);
        const originalHtml = $btn.html();
        const $payNowBtn = $('button[name="o_payment_submit_button"]');

        $btn.prop('disabled', true)
            .html('<span class="spinner-border spinner-border-sm"></span> Processing...');
        $payNowBtn.prop('disabled', true);

        try {
            const response = await fetch('/payment/myfatoorah/applepay/pay', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} }),
            });

            if (!response.ok) throw new Error(`Server error: ${response.status}`);

            const data = await response.json();
            console.log('MF Apple Pay Response:', data);
            const result = data.result;

            if (result && result.success && result.redirect_url) {
                // Store order info in sessionStorage as backup
                // before leaving the page
                if (result.order_id) {
                    sessionStorage.setItem('mf_apple_pay_order_id', result.order_id);
                }
                sessionStorage.setItem('mf_apple_pay_in_progress', '1');

                window.top.location.href = result.redirect_url;
            } else {
                throw new Error(result?.message || 'Failed to generate payment link.');
            }

        } catch (error) {
            console.error('Apple Pay Error:', error);
            alert(error.message || 'An unexpected error occurred.');
            $btn.prop('disabled', false).html(originalHtml);
            $payNowBtn.prop('disabled', false);
        }
    },
});

export default publicWidget.registry.MyFatoorahApplePay;
