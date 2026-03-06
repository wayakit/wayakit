/** @odoo-module **/

import PaymentForm from "@payment/js/payment_form";
import WebsiteSaleTrackingAlternative from "@website_sale_tracking_base/js/website_sale_tracking";

PaymentForm.include({
    /**
     * @override
     * @param {Event} ev
     * @return {void}
     */
    async _submitForm(ev) {
        ev.stopPropagation();
        ev.preventDefault();
        const _super = this._super.bind(this);
        if (document.querySelector('.o_portal_sidebar')) {
            let websiteSaleTracking = new WebsiteSaleTrackingAlternative(this);
            if (websiteSaleTracking.trackingIsLogged()) { console.log('[Tracking] Purchase Portal') }
            await websiteSaleTracking.trackingExecuteEvent({
                event_type: 'purchase_portal',
                order_id: parseInt(this.$el.data('orderId')) || null,
            });
        }
        return _super(...arguments);
    },
});

export default PaymentForm;
