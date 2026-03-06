# Copyright © 2019 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License OPL-1 (https://www.odoo.com/documentation/15.0/legal/licenses.html).

from odoo import api, models


class Website(models.Model):
    _inherit = "website"

    @api.model
    def _tracking_event_mapping(self, service_type):
        res = super(Website, self)._tracking_event_mapping(service_type)
        if service_type == 'fbp':
            # https://developers.facebook.com/docs/meta-pixel/reference
            res = {
                'sign_up': 'CompleteRegistration',
                'view_product': 'ViewContent',
                'view_product_list': 'ViewContent',
                'search_product': 'Search',
                'add_to_wishlist': 'AddToWishlist',
                'add_to_cart': 'AddToCart',
                'begin_checkout': 'InitiateCheckout',
                'add_payment_info': 'AddPaymentInfo',
                'purchase': 'Purchase',
                'purchase_portal': 'Purchase',
            }
        return res

    def _fbp_allowed_services(self):
        self.ensure_one()
        return self.sudo().tracking_service_ids.filtered(lambda s: s.type == 'fbp' and s.active)

    def _fbp_params(self):
        self.ensure_one()
        res = super(Website, self)._fbp_params()
        params = res[:1]  # Get the consent param only

        for service in self._fbp_allowed_services():
            params.append({
                'action': 'init',
                'key': service.key,
                'extra_vals': service.get_visitor_data(),
            })
        return params

    def fbp_get_primary_key(self):
        super(Website, self).fbp_get_primary_key()
        primary_service = self._fbp_allowed_services()
        return primary_service and primary_service[0].key or ''

    def _tracking_do_logging(self, service) -> bool:
        """ The Internal Logging can be used internally in a company for analytics or marketing purposes, so
            The logic prevents to make internal logging if no one of these consents is granted.
        """
        self.ensure_one()
        do_logging = super(Website, self)._tracking_do_logging(service)
        if service.type != 'fbp':
            return do_logging
        return do_logging and (self._cookies_analytics_is_granted() or self._cookies_marketing_is_granted())
