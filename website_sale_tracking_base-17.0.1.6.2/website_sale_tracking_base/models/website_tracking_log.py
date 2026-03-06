# Copyright © 2023 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License OPL-1 (https://www.odoo.com/documentation/15.0/legal/licenses.html).

import json
from datetime import datetime, timedelta
from hashlib import sha256
import logging

from odoo import api, fields, models
from odoo.addons.phone_validation.tools import phone_validation
from odoo.addons.base.models.res_country import Country
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from .website import TRACKING_EVENT_TYPES

_logger = logging.getLogger(__name__)


class WebsiteTrackingLog(models.Model):
    _name = "website.tracking.log"
    _description = 'Website Tracking Event Logs'
    _order = 'create_date DESC'

    service_id = fields.Many2one(
        comodel_name='website.tracking.service',
        ondelete='cascade',
        required=True,
    )
    website_id = fields.Many2one(
        related='service_id.website_id',
        store=True,
    )
    service_type = fields.Selection(
        related='service_id.type',
        store=True,
    )
    event_type = fields.Selection(
        selection=TRACKING_EVENT_TYPES,
        required=True,
    )
    custom_event_id = fields.Many2one(
        comodel_name='website.tracking.event',
        string='Custom Event',
    )
    is_custom_events_allowed = fields.Boolean(related='service_id.is_custom_events_allowed')
    payload = fields.Char(readonly=True)
    payload_preview = fields.Char(compute='_compute_payload_preview')
    product_ids = fields.Many2many(
        comodel_name='product.product',
        string='Products',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        compute='_compute_product_id',
        store=True,
    )
    order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sale Order',
        ondelete='cascade',
    )
    url = fields.Char(string='URL')
    visitor_id = fields.Many2one(comodel_name='website.visitor', ondelete='set null')
    country_id = fields.Many2one(comodel_name='res.country', readonly=True)
    country_flag = fields.Char(related="country_id.image_url", string="Country Flag")
    search_term = fields.Char()
    # API related fields
    channel = fields.Selection(
        selection=[('js_script', 'JS Script')],
        string='Data Channel',
        default='js_script',
    )
    state = fields.Selection(
        selection=[
            ('internal', 'Internal'),
            ('to_send', 'To Send'),
            ('sent', 'Sent'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        ],
    )
    api_send_is_denied = fields.Boolean(
        string="Don't Send by API",
        help="If this option is activated this event will no be sent by API.",
    )
    api_response = fields.Text(string='API Response')
    api_sent_date = fields.Datetime(string='API Sent Date')
    # Website visitor's data
    user_agent = fields.Char(default='')
    user_ip_address = fields.Char(default='')

    @api.depends('payload')
    def _compute_payload_preview(self):
        for log in self:
            try:
                log.payload_preview = json.dumps(json.loads(log.payload), indent=2)
            except TypeError:
                log.payload_preview = ''

    @api.depends('product_ids')
    def _compute_product_id(self):
        for log in self:
            if log.product_ids and len(log.product_ids) == 1:
                log.product_id = log.product_ids[0].id
            else:
                log.product_id = False

    @api.model
    def _hash_sha256(self, value: str):
        return sha256(value.encode('utf-8')).hexdigest()

    @api.model
    def _to_unix_time(self, date_value: datetime):
        return round(date_value.timestamp())

    @api.model
    def _hash_email(self, email: str) -> str:
        return self._hash_sha256(email.lower())

    @api.model
    def _format_phone_number(self, number: str, country: Country, remove_plus: bool = False) -> str:
        phone_number = number
        if country and number:
            phone_number = phone_validation.phone_format(
                number,
                country_code=country.code,
                country_phone_code=country.phone_code,
                force_format='E164',
                raise_exception=False,
            )
        if remove_plus:
            phone_number = phone_number.replace('+', '')
        return phone_number

    @api.depends('service_id', 'event_type')
    def _compute_display_name(self):
        for log in self:
            log.display_name = "%s (%s)" % (log.service_id.display_name, log.event_type)

    def action_send_event(self):
        """Method to send request via API. To override."""
        self.ensure_one()

    @api.model
    def _get_fields_to_clean_up(self):
        return ['payload', 'user_agent', 'user_ip_address']

    @api.autovacuum
    def _gc_clean_up_payload_and_visitor_sensitive_data(self):
        # flake8: noqa: E501
        try:
            period = int(self.env['ir.config_parameter'].sudo().get_param('website_sale_tracking_base.log_clean_up_period', 30))
            unlink_mode = bool(self.env['ir.config_parameter'].sudo().get_param('website_sale_tracking_base.log_clean_up_unlink'))
            timeout_ago = datetime.utcnow() - timedelta(days=period)
            domain = [('create_date', '<', timeout_ago.strftime(DEFAULT_SERVER_DATETIME_FORMAT))]
            logs_sudo = self.env['website.tracking.log'].sudo().search(domain)
            if unlink_mode:
                return logs_sudo.unlink()
            return logs_sudo.write({fld: '' for fld in self._get_fields_to_clean_up()})
        except Exception as e:
            _logger.error("Error on cleaning of website tracking logs by a cron.")
