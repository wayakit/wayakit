/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.websiteAuthTracking = publicWidget.registry.websiteSaleTrackingAlternative.extend({
    selector: '.oe_website_login_container',
    events: {
        'click form.oe_login_form div.oe_login_buttons button.btn-primary': '_onClickLoginButton',
        'click form.oe_signup_form div.oe_login_buttons button.btn-primary': '_onClickSignupButton',
    },
    _onClickLoginButton: function () {
        this.trigger_up('tracking_login');
    },
    _onClickSignupButton: function () {
        this.trigger_up('tracking_sign_up');
    },
});

export default publicWidget.registry.websiteAuthTracking;
