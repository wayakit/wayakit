/** @odoo-module **/

import "@website/snippets/s_website_form/000";  // force dependencies
import publicWidget from '@web/legacy/js/public/public_widget';

var websiteSaleTrackingAlternative = publicWidget.registry.websiteSaleTrackingAlternative;

publicWidget.registry.s_website_form.include({
    send: async function (e) {
        e.preventDefault(); // Prevent the default submit behavior
        const _super = this._super.bind(this);
         // Prevent users from crazy clicking
        const $button = this.$el.find('.s_website_form_send, .o_website_form_send');
        $button.addClass('disabled').attr('disabled', 'disabled');

        if (this.check_error_fields({})) {
            let websiteSaleTracking = new websiteSaleTrackingAlternative(this);
            if (websiteSaleTracking.trackingIsLogged()) {
                console.log(websiteSaleTracking.trackingLogPrefix + 'Lead (Contact Us)');
            }
            await websiteSaleTracking.trackingExecuteEventSync({
                event_type: 'lead',
            });
            // Additional waiting time for initiating
            // requests intended to send data to tracking services.
            const superWithTimeout = (delay) => new Promise(
                (resolve) => setTimeout(() => { return _super(...arguments) }, delay)
            );
            return await superWithTimeout(2000);
        }
        return _super(...arguments);
    },
});

export default publicWidget.registry.s_website_form;
