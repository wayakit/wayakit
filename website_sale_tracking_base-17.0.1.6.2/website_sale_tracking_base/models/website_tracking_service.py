# Copyright © 2023 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License OPL-1 (https://www.odoo.com/documentation/15.0/legal/licenses.html).

from typing import Dict, List, Set
from urllib.parse import parse_qs, urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.models import BaseModel


class WebsiteTrackingService(models.Model):
    _name = "website.tracking.service"
    _inherit = ['mail.thread']
    _description = 'Service that gets Tracking Event Data'
    _order = 'sequence, website_id, type'

    def _default_website(self):
        return self.env['website'].search([('company_id', '=', self.env.company.id)], limit=1)  # flake8: noqa: E501

    # flake8: noqa: E501
    type = fields.Selection(selection=[])
    key = fields.Char(tracking=True)
    key_is_required = fields.Boolean(default=True, tracking=True)
    cookie_type = fields.Selection(selection=[])
    website_id = fields.Many2one(
        comodel_name='website',
        ondelete='cascade',
        default=_default_website,
        required=True,
    )
    item_type = fields.Selection(
        selection=[
            ('product.template', 'Product Template ID'),
            ('product.product', 'Product Variant ID'),
        ],
        default='product.template',
        required=True,
    )
    category_type = fields.Selection(
        selection=[
            ('public', 'Public Category (with hierarchy)'),
            ('product', 'Product Category'),
        ],
        default='public',
        required=True,
    )
    event_ids = fields.One2many(
        comodel_name='website.tracking.event',
        inverse_name='service_id',
        string='Custom Events',
    )
    is_custom_events_allowed = fields.Boolean(string='Custom events are allowed', default=False)
    is_internal_logged = fields.Boolean(string="Internal Logs", tracking=True)
    sequence = fields.Integer(default=100)
    active = fields.Boolean(default=True, tracking=True)
    # Advanced Matching
    privacy_url = fields.Char(string='Data Use Privacy URL', readonly=True)
    track_id_external = fields.Boolean(string="Track External ID", tracking=True)
    external_id_type = fields.Selection(
        selection=[
            ('auto', 'Auto'),
            ('partner_id', 'Partner ID'),
            ('partner_email', 'Partner Email'),
        ],
        string='ID Type',
        default='auto',
        required=True,
    )
    track_ip_address = fields.Boolean(string="Track IP Address", tracking=True)
    track_user_agent = fields.Boolean(tracking=True)
    track_user_name = fields.Boolean(string="Customer Name", tracking=True)
    user_name_is_hashed = fields.Boolean(string='Hash user names', default=True)
    track_email = fields.Boolean(tracking=True)
    email_is_hashed = fields.Boolean(string='Hash an e-mail', default=True)
    track_phone = fields.Boolean(tracking=True)
    phone_is_hashed = fields.Boolean(string='Hash a phone number', default=True)
    track_country = fields.Boolean(tracking=True)
    track_zip = fields.Boolean(tracking=True)
    track_state = fields.Boolean(tracking=True)
    track_city = fields.Boolean(tracking=True)
    track_street = fields.Boolean(tracking=True)
    street_is_hashed = fields.Boolean(string='Hash a street', default=False)
    track_customer_data_source = fields.Selection(
        selection=[
            ('visitor', 'Website Visitor'),
            ('sale_order', 'Sale Order Partner'),
        ],
        string='Customer Data Source',
        help='It determines a source where the solution gets data about a website visitor. '
             'The source can be the "Website Visitor" record, that is created for each unauthorized visitor of your '
             'website. In this case, the solution does not have enough user data, like as email, phone, etc., '
             'to sent to external services. These data can be retrieved after the visitor logging into the portal. '
             'And the second option the "Partner from Sale Order", in this case user data can be retrieved from '
             'the "Partner" record of the last visitor sale order. So, just the visitor completes the first order, '
             'the solution can get his/her data and sent it to external services.',
        default='sale_order',
        tracking=True,
    )
    lead_value = fields.Float(default=1.0, help="A lead value for the Contact Us form.")
    show_lead_value = fields.Boolean(compute='_compute_show_lead_value')
    # API
    api_is_active = fields.Boolean(string='API', help='Send event data via API (server-side).')
    api_is_available = fields.Boolean(compute='_compute_api_is_available')
    api_token = fields.Char(string='Access Token')
    api_test_code = fields.Char(
        string='Test Code',
        help='If you activate this option, the API will work in the Test Mode. '
             'Use this option to test your server events if the tracking service allows that.',
    )
    api_deactivate_pixel = fields.Boolean(
        string='Remove JS Pixel script',
        help='If you activate this option, the Pixel script will be removed from website. '
             'So, tracking data will be sent only by Conversions/Events API.',
    )

    @api.model
    def _get_available_visitor_data(self) -> Set[str]:
        """ Define a full list of user data tracking field names. """
        return {
            'track_user_name', 'track_id_external', 'track_ip_address', 'track_user_agent',
            'track_email', 'track_phone', 'track_country', 'track_city', 'track_zip', 'track_street', 'track_state',
        }

    def _get_allowed_visitor_data(self) -> List[Dict[str, str or Set[str]]]:
        """
        Define what user data tracking can be activated for the specific service.
        Return a structure of allowed user data for the current service.
        Method to override.
        """
        self.ensure_one()
        return []

    @api.constrains(
        'type', 'track_user_name', 'track_id_external', 'track_ip_address', 'track_user_agent',
        'track_email', 'track_phone', 'track_country', 'track_city', 'track_zip', 'track_street', 'track_state',
    )
    def _check_available_visitor_data(self):
        """ Define what website visitor data can be activated in a service. """
        for service in self:
            for service_data in service._get_allowed_visitor_data():
                if service.type != service_data['service']:
                    continue
                available_field_set = service_data['script'] if not service.api_is_active else service_data['api']
                restricted_field_set = self._get_available_visitor_data() - available_field_set
                if any(service[track_option] for track_option in restricted_field_set):
                    raise ValidationError(
                        _('Only the following data can be sent to this service:\n%s') % '\n'.join(available_field_set)
                    )

    @api.constrains('is_internal_logged', 'api_is_active')
    def _check_api_is_internal_logged(self):
        for service in self:
            if service.api_is_active and not service.is_internal_logged:
                raise ValidationError(_("You have to activate internal logging for services with the API connection."))

    @api.depends('type')
    def _compute_api_is_available(self):
        """ Indicate what tracking services can use API to send event data. Method to override."""
        for service in self:
            service.api_is_available = False

    @api.depends('type')
    def _compute_show_lead_value(self):
        for service in self:
            service.show_lead_value = 'lead' in self.env['website']._tracking_event_mapping(service.type).keys()

    @api.depends('type', 'key')
    def _compute_display_name(self):
        for service in self:
            service.display_name = "%s%s" % (
                dict(self._fields['type'].selection).get(service.type),
                service.key and f": {service.key}" or ''
            )

    def allow_send_data(self):
        """Method to check additional restrictions. To override."""
        self.ensure_one()
        return self.active and self.key

    def get_item(self, item_data: Dict):
        self.ensure_one()
        service = self
        template_id = item_data.get('product_tmpl_id')
        variant_id = item_data.get('product_id')
        if service.item_type == 'product.template':
            product = self.env['product.template'].browse(template_id)
        elif service.item_type == 'product.product':
            product = self.env['product.product'].browse(variant_id)
        else:
            product = None
        return product

    def get_item_categories(self, product, property_name: str = 'content_category') -> Dict:
        """Generate a product category hierarchy structure.
        :param product: a record of the "product.product" model
        """
        self.ensure_one()
        res = {}
        if self.category_type == 'product':
            res.update({property_name: product.categ_id.name})
        elif self.category_type == 'public':
            # Use the first public category of a product
            if product.public_categ_ids[:1]:
                category = product.public_categ_ids[:1].name
            else:
                category = _('All products')
            res.update({property_name: category})
        return res

    def get_common_data(self, event_type, product_data_list=None, order=None, pricelist=None):
        self.ensure_one()
        return {}

    def get_custom_event_data(self, custom_event, product_data_list=None, order=None, pricelist=None):
        self.ensure_one()
        return {}

    def get_item_data_from_product_list(self, product_data_list, pricelist) -> Dict:
        """Prepare data for a tracking service from a product data list.
        :param product_data_list: a list with product data (take a look at "controllers/main.py")
        :param pricelist: a record of the model "product.pricelist"
        """
        self.ensure_one()
        return {}

    def get_item_data_from_order(self, order) -> Dict:
        """Prepare data for a tracking service from a sale order.
        :param order: a record of the model "sale.order"
        """
        self.ensure_one()
        return {}

    def _get_final_product_price(self, order_line) -> float:
        self.ensure_one()
        if self.env.user.has_group('account.group_show_line_subtotals_tax_excluded'):
            price = order_line.price_reduce_taxexcl
        elif self.env.user.has_group('account.group_show_line_subtotals_tax_included'):
            price = order_line.price_reduce_taxinc
        else:
            price = order_line.price_unit
        return price

    def get_data_for_lead(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return {'value': self.lead_value}

    def get_data_for_login(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return {}

    def get_data_for_sign_up(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return {}

    def get_data_for_view_product_list(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_product_list(product_data_list, pricelist)

    def get_data_for_view_product_category(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_product_list(product_data_list, pricelist)

    def get_data_for_search_product(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_product_list(product_data_list, pricelist)

    def get_data_for_view_product(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_product_list(product_data_list, pricelist)

    def get_data_for_add_to_wishlist(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_product_list(product_data_list, pricelist)

    def get_data_for_add_to_cart(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_product_list(product_data_list, pricelist)

    def get_data_for_update_cart(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_product_list(product_data_list, pricelist)

    def get_data_for_remove_from_cart(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_product_list(product_data_list, pricelist)

    def get_data_for_begin_checkout(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_order(order)

    def get_data_for_add_shipping_info(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_order(order)

    def get_data_for_add_payment_info(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_order(order)

    def get_data_for_purchase(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_order(order)

    def get_data_for_purchase_portal(self, product_data_list=None, pricelist=None, order=None):
        self.ensure_one()
        return self.get_item_data_from_order(order)

    @api.model
    def _normalize_value(self, value: str, remove_symbols: List[str] = None) -> str:
        res = str(value)
        res = res.strip()
        res = res.lower()
        if remove_symbols:
            for symbol in remove_symbols:
                res = res.replace(symbol, '')
        return res

    def _visitor_data_mapping(self):
        """Return dictionary with mappings of visitor data params
        for specific type of tracking service. Method to override."""
        self.ensure_one()
        return {
            'external_ref': {'name': 'external_ref', 'hash': True},
            'first_name': {'name': 'first_name', 'hash': True},
            'last_name': {'name': 'last_name', 'hash': True},
            'email': {'name': 'email', 'hash': True},
            'phone':  {'name': 'phone', 'hash': True, 'remove_plus': False},
            'street':  {'name': 'street', 'hash': True},
            'city':  {'name': 'city', 'hash': True},
            'zip':  {'name': 'zip', 'hash': True},
            'state':  {'name': 'state', 'hash': True},
            'country':  {'name': 'country', 'hash': True},
            'ip_address':  {'name': 'ip_address', 'hash': False},
            'user_agent':  {'name': 'user_agent', 'hash': False},
        }

    # pylint: disable-msg=too-many-locals,too-many-branches,too-many-statements
    def get_visitor_data(self, visitor_id: int = None, sale_order_id: int = None, log_id: int = None) -> Dict:
        self.ensure_one()
        service = self
        visitor_data = {}

        # Determine to use a request to get data about a current visitor
        use_request = self._context.get('data_from_request', True) and bool(request)

        sale_order = self.env['sale.order'].sudo().browse(sale_order_id) if sale_order_id \
            else request.website.sale_get_order() if use_request else None
        # If a visitor is not logged, but he has completed checkout before, use the user data from the previous order
        # Also, on the checkout confirmation page it's impossible to get an order from the request,
        # so get it from the session
        if (use_request and (
                sale_order and sale_order.partner_id == self.env.ref('base.public_partner') or not sale_order
        )):
            sale_order = self.env['sale.order'].sudo().browse(request.session.get('sale_last_order_id', 0))

        visitor = self.env['website.visitor'].sudo().browse(visitor_id)

        # Get customer data from a sale order in priority if this option is checked
        if (
                sale_order and sale_order.exists() and service.track_customer_data_source == 'sale_order'
                and sale_order.partner_id != self.env.ref('base.public_partner')
        ):
            partner = sale_order.partner_id
            # If a sale order is made by a customer which is not logged in, use the External ID of a visitor
            external_ref = visitor.access_token if visitor and visitor.partner_id != partner else str(partner.id)
            email = partner.email
            country = partner.country_id
            phone = partner.phone or partner.mobile

        # Otherwise, get customer data from a visitor
        else:
            if not visitor:
                visitor = self.env['website.visitor']._get_visitor_from_request(force_create=False)
            if not visitor:
                # Return an empty data
                return visitor_data

            partner = visitor.partner_id
            external_ref = visitor.access_token
            email = visitor.email
            country = partner.country_id or visitor.country_id
            phone = partner and (partner.phone or partner.mobile) or visitor.mobile

        if service.external_id_type == 'partner_id':
            external_ref = str(partner.id) if partner else ''
        elif service.external_id_type == 'partner_email':
            external_ref = email or ''

        log = self.env['website.tracking.log']
        mappings = service._visitor_data_mapping()

        def _add_visitor_data(option: str, mapping_key: str,  value: str or bool or BaseModel, force_hashing: bool = None):
            k_mapping = mappings.get(mapping_key)
            if getattr(service, option, False) and value and k_mapping:
                key = k_mapping['name']
                if isinstance(value, BaseModel):
                    field_name = k_mapping.get('field_name')
                    value = value['name'] if not field_name else value[field_name]
                # Special cases
                if mapping_key in ['email']:
                    value = self._normalize_value(value, remove_symbols=k_mapping.get('remove_symbols'))
                if k_mapping.get('normalize'):
                    value = self._normalize_value(value, remove_symbols=k_mapping.get('remove_symbols'))
                if k_mapping.get('lowercase'):
                    value = value.lower()
                # Additional processing
                if force_hashing is True or force_hashing is None and k_mapping.get('hash'):
                    value = log._hash_sha256(value)
                    if k_mapping.get('name_hashed_alias'):
                        key = k_mapping.get('name_hashed_alias')
                if k_mapping.get('type') == 'list':
                    value = [value]
                return {key: value}
            return {}

        visitor_data.update(_add_visitor_data('track_id_external', 'external_ref', external_ref))
        if country:
            visitor_data.update(_add_visitor_data('track_country', 'country', country))
        if partner.state_id:
            visitor_data.update(_add_visitor_data('track_state', 'state', partner.state_id))
        visitor_data.update(_add_visitor_data('track_zip', 'zip', partner.zip))
        visitor_data.update(_add_visitor_data('track_city', 'city', partner.city))
        visitor_data.update(_add_visitor_data('track_street', 'street', partner.street, service.street_is_hashed))
        visitor_data.update(_add_visitor_data('track_email', 'email', email, service.email_is_hashed))
        # Process a phone number
        if service.track_phone and phone and country:
            phone_number = log._format_phone_number(
                phone, country, remove_plus=mappings.get('phone', {}).get('remove_plus', False),
            )
            visitor_data.update(_add_visitor_data('track_phone', 'phone', phone_number, service.phone_is_hashed))
        # Process customer names
        if partner and partner != self.env.ref('base.public_partner'):
            user_names = self._normalize_value(partner.name).split(' ')
            for index, name in enumerate(user_names[:2]):
                visitor_data.update(_add_visitor_data(
                    option='track_user_name',
                    mapping_key=f"{service.website_id.tracking_user_name_order.split('_')[index]}_name",
                    value=name,
                    force_hashing=service.user_name_is_hashed,
                ))

        request_data = self._context.get('request_data', {})
        tracking_log = log.browse(log_id)
        if request_data:
            # Process a request related data
            visitor_data.update(_add_visitor_data('track_ip_address', 'ip_address', request_data.get('ip')))
            visitor_data.update(_add_visitor_data('track_user_agent', 'user_agent', request_data.get('user_agent')))
        elif tracking_log:
            # If there is no a request and a tracking log is passed, use data from the tracking log
            visitor_data.update(_add_visitor_data('track_ip_address', 'ip_address', tracking_log.user_ip_address))
            visitor_data.update(_add_visitor_data('track_user_agent', 'user_agent', tracking_log.user_agent))

        return visitor_data

    def complete_user_data(self, user_data: Dict) -> Dict:
        """ Supplement or transform user data for the specific service. Method to override. """
        self.ensure_one()
        return user_data

    @api.model
    def _get_privacy_url(self) -> Dict:
        return {}

    @api.model
    def _get_url_query_param(self, url: str, param_name: str) -> str:
        """ Get URL parameters from URLs and return them as a dictionary. """
        parse_res = urlparse(url)
        param_list = parse_qs(parse_res.query).get(param_name, [])
        return param_list[0] if param_list else ''

    @api.model
    def _get_subdomain_index(self, url: str) -> int:
        """ Calculate the URL subdomain index, like that: 'com' = 0, 'example.com' = 1, 'www.example.com' = 2 """
        parse_res = urlparse(url)
        res = len(parse_res.netloc.split('.')) - 1
        return res

    @api.model
    def _with_custom_events_allowed(self) -> List[str]:
        """ A list of tracking service types that are allowed to use custom events. """
        return []

    @api.model
    def _fields_to_invalidate_cache(self) -> List[str]:
        return [
            'sequence', 'website_id', 'key', 'active',
            'track_id_external', 'track_user_name', 'user_name_is_hashed',
            'track_email', 'email_is_hashed', 'track_phone', 'phone_is_hashed',
            'track_country', 'track_state', 'track_zip', 'track_city', 'track_street', 'street_is_hashed',
            'api_is_active', 'api_deactivate_pixel',
        ]

    @api.model_create_multi
    def create(self, vals_list):
        # Set up a default privacy URL for a tracking services
        for vals in vals_list:
            service_type = vals.get('type')
            if service_type and self._get_privacy_url().get(service_type):
                vals['privacy_url'] = self._get_privacy_url().get(service_type)
            if service_type in self._with_custom_events_allowed():
                vals['is_custom_events_allowed'] = True
        record = super(WebsiteTrackingService, self).create(vals_list)
        # Invalidate the caches to apply changes on webpages
        self.env.registry.clear_cache()
        return record

    def write(self, vals):
        result = super(WebsiteTrackingService, self).write(vals)
        if any(fld in vals for fld in self._fields_to_invalidate_cache()):
            # Invalidate the caches to apply changes on webpages
            self.env.registry.clear_cache()
        return result

    def extra_log_data(self):
        """Add extra values on to the "log" record. Method to override."""
        self.ensure_one()
        return {}

    def post_processed_data(self, event_data: Dict) -> Dict:
        """Perform post-processing of event data. Return a dictionary to update.
           Method to override.
        """
        self.ensure_one()
        return {}
