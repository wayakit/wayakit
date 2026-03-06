/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.websiteSaleTrackingAlternative = publicWidget.Widget.extend({
    selector: '.oe_website_sale',
    events: {
        'click button.o_add_wishlist_dyn': 'trackingEventAddToWishlist',
        'click button.o_add_wishlist': 'trackingEventAddToWishlistFromList',
        'click button.o_wish_add': 'trackingEventAddToCartFromList',
        'click #add_to_cart': 'trackingEventAddToCart',
        'click div.o_wsale_product_grid_wrapper form[action="/shop/cart/update"] a.a-submit': 'trackingEventAddToCartFromList',
        'click a[href*="/shop/checkout"]': 'trackingEventBeginCheckout',
        'click a[href="#"].a-submit-loading': 'trackingEventAddShippingInfo',
    },
    custom_events: {
        tracking_login: 'trackingEventLogin',
        tracking_sign_up: 'trackingEventSignUp',
        tracking_payment_info: 'trackingEventAddPaymentInfo',
    },

    trackingIsLogged: function() {
        const logTrackingEvents = document.querySelector('body').getAttribute('data-log-tracking-events');
        return (typeof logTrackingEvents !== 'undefined' && logTrackingEvents)
    },
    
    init: function() {
        this._super.apply(this, arguments);
        this.rpc = this.bindService("rpc");
        this.trackingLogPrefix = '[Tracking] ';
    },

    start: function (ev) {
        let self = this;

        // view_item
        const $productView = this.$('div#product_details')
        if ($productView.length) {
            if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'View Product') }
            let params = this.trackingGetProductParams();
            params['event_type'] = 'view_product';
            this.trackingExecuteEvent(params);
        }
        // view_item_list or search
        const $productsGrid = this.$('div#products_grid')
        if ($productsGrid.length) {
            let productTemplateIds = $productsGrid.attr('data-tracking_product_tmpl_ids');
            let productCategory = $productsGrid.attr('data-tracking_category')
            if (productTemplateIds) {
                if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'View Product List') }
                this.trackingExecuteEvent({
                    event_type: 'view_product_list',
                    product_ids: productTemplateIds && JSON.parse(productTemplateIds) || [],
                    product_category: parseInt(productCategory, 10),
                });
            }
            if (productCategory) {
                if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'View Product Category') }
                this.trackingExecuteEvent({
                    event_type: 'view_product_category',
                    product_ids: productTemplateIds && JSON.parse(productTemplateIds) || [],
                    product_category: parseInt(productCategory, 10),
                });
            }
            let searchTerm = $productsGrid.attr('data-tracking_search_term')
            if (searchTerm) {
                if (self.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Search') }
                this.trackingExecuteEvent({
                    event_type: 'search_product',
                    search_term: searchTerm,
                    product_ids: productTemplateIds && JSON.parse(productTemplateIds) || [],
                });
            }
        }
        // purchase
        const $confirmation = this.$('div.oe_website_sale_tx_status');
        if ($confirmation.length) {
            if (self.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Purchase') }
            this.trackingExecuteEvent({
                event_type: 'purchase',
                order_id: parseInt($confirmation.data('order-id'), 10),
            });
        }
        return this._super.apply(this, arguments);
    },

    trackingEventLogin: function (ev) {
        if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'User Login') }
        this.trackingExecuteEvent({ event_type: 'login' });
    },

    trackingEventSignUp: function (ev) {
        if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Sign Up') }
        this.trackingExecuteEvent({ event_type: 'sign_up' });
    },

    trackingEventAddToWishlist: function (ev) {
        if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Add To Wishlist (Product)') }
        let params = this.trackingGetProductParams();
        params['event_type'] = 'add_to_wishlist';
        this.trackingExecuteEvent(params);
    },

    trackingEventAddToWishlistFromList: function (ev) {
        if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Add To Wishlist (Product List)') }
        let params = this.trackingGetProductParams(ev.currentTarget.parentNode);
        params['event_type'] = 'add_to_wishlist';
        this.trackingExecuteEvent(params);
    },

    trackingEventAddToCart: function (ev) {
        if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Add To Cart (Product)') }
        let params = this.trackingGetProductParams();
        params['event_type'] = 'add_to_cart';
        this.trackingExecuteEvent(params);
    },

    trackingEventAddToCartFromList: function (ev) {
        if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Add To Cart (Product List)') }
        let params = this.trackingGetProductParams(ev.currentTarget.parentNode);
        params['event_type'] = 'add_to_cart';
        this.trackingExecuteEvent(params);
    },

    trackingEventBeginCheckout: function (ev) {
        if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Begin Checkout') }
        this.trackingExecuteEvent({ event_type: 'begin_checkout' });
    },

    trackingEventAddShippingInfo: function(ev) {
        if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Add Shipping Info') }
        this.trackingExecuteEvent({ event_type: 'add_shipping_info' });
    },

    trackingEventAddPaymentInfo: async function(ev) {
        if (this.trackingIsLogged()) { console.log(this.trackingLogPrefix + 'Add Payment Info') }

        const checkedRadio = document.querySelector('input[name="o_payment_radio"]:checked');
        // console.log(checkedRadio.dataset);
        let params = {
            event_type: 'add_payment_info',
            payment_provider_id: parseInt(checkedRadio.dataset.providerId, 10),
            // provider_code: checkedRadio.dataset.providerCode,
            // payment_method_code: checkedRadio.dataset.paymentMethodCode
        }
        this.trackingExecuteEvent(params);
    },

    trackingGetProductParams: function(el) {
        let my_elem = document;
        if (el) { my_elem = el }
        let params = {};

        let product_template_id = my_elem.querySelector('input[name="product_template_id"]');
        // console.log(`alt_pr_tmpl=${product_template_id}, value=${product_template_id.value}, type_of_value=${typeof product_template_id.value}`);
        if (!product_template_id || product_template_id && typeof product_template_id.value !== 'string') {
            product_template_id = my_elem.querySelector('input[name="alt_product_template_id"]');
        }
        let product_id = my_elem.querySelector('input[name="product_id"]');
        // console.log(`alt_pr=${product_id}, value=${product_id.value}, type_of_value=${typeof product_id.value}`);
        if (!product_id || product_id && typeof product_id.value !== 'string') {
            product_id = my_elem.querySelector('input[name="alt_product_id"]');
        }
        let add_qty = my_elem.querySelector('input[name="add_qty"]');

        if (
            product_id && typeof product_id.value !== 'string'
            && product_template_id && typeof product_template_id.value !== 'string'
            || !product_id && !product_template_id
        ) {
            if (this.trackingIsLogged()) {
                console.log('[Tracking] There is no product or product template ID. Might the website customizations take a place.');
            }
            return params;
        }

        // Select "product_id" on prior way
        if (product_id && product_id.value && product_id.value !== '0') {  // Skip dynamic product variants with ID = 0
            params['item_type'] = 'product.product';
            params['product_ids'] = [parseInt(product_id.value, 10)];
        } else {
            params['item_type'] = 'product.template';
            params['product_ids'] = [parseInt(product_template_id.value, 10)];
        }
        if (add_qty && add_qty.value) {
            params['product_qty'] = parseInt(add_qty.value, 10);
        }

        if (this.trackingIsLogged()) {
            console.log(this.trackingLogPrefix + 'Item Parameters:');
            console.log(params);
        }
        return params;
    },

    _processTrackingResponse: function(response, eventType) {
        if (this.trackingIsLogged()) {
            if (response['error']) {
                console.log(this.trackingLogPrefix + 'ERROR: ' + response['error']);
            }
            console.log('>>> trackingResponse:');
            console.log(response);
        }
        if (response['services'] !== undefined && response['services']) {
            this.trackingSendEventData(eventType, response['services']);
        }
    },

    trackingExecuteEvent: function(params) {
        let self = this
        return this.rpc(
            "/website/tracking_data", params,
        ).then((trackingResponse) => {
            self._processTrackingResponse(trackingResponse, params['event_type']);
        }).catch(error => console.log(error))
    },

    // For cases where we need to perform tracking synchronously
    // (for example, if the super method initiates a transition
    // to another page and we need to perform a tracking request before that)
    trackingExecuteEventSync: async function(params) {
        const response = await this.rpc("/website/tracking_data", params);
        this._processTrackingResponse(response, params['event_type']);
    },

    trackingSendEventData: function(eventType, eventData) {
        if (this.trackingIsLogged()) {
            console.log('-- SEND DATA --');
        }
    },

});

export default publicWidget.registry.websiteSaleTrackingAlternative;
