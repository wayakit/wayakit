/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.websiteSaleTrackingAlternative.include({

    _trackingFacebookPixel: function () {
        const websiteFBP = window.fbq || function () {};
        if (this.trackingIsLogged()) {
            console.log('DO _trackingFacebookPixel');
        }
        websiteFBP.apply(this, arguments);
    },

    trackingSendEventData: function(eventType, eventData) {
        if (this.trackingIsLogged()) { console.log('-- RUN Facebook Pixel --') }
        if (eventData['fbp'] !== undefined && Array.isArray(eventData['fbp'])) {
            for(let i = 0; i < eventData['fbp'].length; i++) {
                if (this.trackingIsLogged()) {
                    console.log(eventData['fbp'][i]);
                }
                let run_script = eventData['fbp'][i]['run_script'];
                let event_name = eventData['fbp'][i]['event_name'];
                let tracking_id = eventData['fbp'][i]['key'];
                let event_data = eventData['fbp'][i]['data'];
                let eventID = eventData['fbp'][i]['event_id'];
                if (event_data !== undefined && run_script !== undefined && run_script === true) {
                    this._trackingFacebookPixel(
                        'trackSingle', tracking_id, event_name, event_data, {'eventID': eventID}
                    );
                }
            }
        }
        return this._super.apply(this, arguments);
    },
});
