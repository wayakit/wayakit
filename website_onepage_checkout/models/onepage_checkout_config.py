from odoo import api, fields, models


class OnepageCheckoutConfig(models.Model):
    _name = 'onepage.checkout.config'
    _description = 'Onepage Checkout Configuration'

    name = fields.Char(
        string='Name',
        required=True,
        default='Default Onepage Checkout Configuration',
    )

    # ── Panel Visibility ──────────────────────────────────────────────
    billing_panel = fields.Boolean(
        string='Billing Information Panel',
        default=True,
    )
    shipping_panel = fields.Boolean(
        string='Shipping Information Panel',
        default=True,
    )
    delivery_panel = fields.Boolean(
        string='Delivery Method Panel',
        default=True,
    )
    payment_panel = fields.Boolean(
        string='Payment Method Panel',
        default=True,
    )

    # ── Panel Labels ──────────────────────────────────────────────────
    billing_label = fields.Char(
        string='Billing Panel Label',
        default='Billing Information',
    )
    shipping_label = fields.Char(
        string='Shipping Panel Label',
        default='Shipping Information',
    )
    delivery_label = fields.Char(
        string='Delivery Panel Label',
        default='Delivery Method',
    )
    payment_label = fields.Char(
        string='Payment Panel Label',
        default='Order Preview and Payment Option',
    )

    # ── Required Fields ───────────────────────────────────────────────
    wk_billing_required = fields.Many2many(
        'billing.default.fields',
        'onepage_checkout_billing_rel',
        'config_id', 'field_id',
        string='Wk Billing Required',
    )
    wk_shipping_required = fields.Many2many(
        'shipping.default.fields',
        'onepage_checkout_shipping_rel',
        'config_id', 'field_id',
        string='Wk Shipping Required',
    )

    # ── Website Scope ─────────────────────────────────────────────────
    for_all_website = fields.Boolean(
        string='For All Website',
        default=True,
    )
    website_id = fields.Many2one(
        'website',
        string='Website Wise',
    )

    # Use is_active (NOT active) to match Webkul pattern.
    # Odoo's 'active' auto-archives records, hiding them from list views.
    is_active = fields.Boolean(string='Active', default=True)

    def toggle_is_active(self):
        """Activate this config and deactivate conflicting ones.
        Only one active config per scope:
          - One 'For All Website' config
          - One config per specific website
        """
        for record in self:
            if record.is_active:
                record.is_active = False
            else:
                # Deactivate configs in the same scope only
                if record.for_all_website:
                    domain = [
                        ('id', '!=', record.id),
                        ('is_active', '=', True),
                        ('for_all_website', '=', True),
                    ]
                else:
                    domain = [
                        ('id', '!=', record.id),
                        ('is_active', '=', True),
                        ('for_all_website', '=', False),
                        ('website_id', '=', record.website_id.id),
                    ]
                self.sudo().search(domain).write({'is_active': False})
                record.is_active = True
