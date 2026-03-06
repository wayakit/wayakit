/** @odoo-module **/

import PaymentForm from '@payment/js/payment_form';
import publicWidget from "@web/legacy/js/public/public_widget";

var websiteSaleTrackingAlternative = publicWidget.registry.websiteSaleTrackingAlternative;

PaymentForm.include({

    async _submitForm (ev) {
        this.saleTracking = new websiteSaleTrackingAlternative(this);
        this.saleTracking.trigger_up('tracking_payment_info');
        return await this._super(...arguments);
    },

});
