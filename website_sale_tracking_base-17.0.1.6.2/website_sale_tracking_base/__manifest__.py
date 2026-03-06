# Copyright © 2023 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License OPL-1 (https://www.odoo.com/documentation/master/legal/licenses.html#odoo-apps).

{
    'name': 'Website | eCommerce Tracking Base',
    'version': '17.0.1.6.2',
    'category': 'eCommerce',
    'author': 'Garazd Creation',
    'website': 'https://garazd.biz/en/odoo-website-tracking',
    'license': 'OPL-1',
    'summary': 'Track Customer Actions on Odoo Website and eCommerce',
    'depends': [
        'website_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter_data.xml',
        'data/ir_filters_data.xml',
        'views/website_views.xml',
        'views/website_sale_templates.xml',
        'views/website_tracking_service_views.xml',
        'views/website_tracking_log_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_sale_tracking_base/static/src/js/website_sale_tracking.js',
            'website_sale_tracking_base/static/src/js/website_sale_cart_tracking.js',
            'website_sale_tracking_base/static/src/js/website_login_tracking.js',
            'website_sale_tracking_base/static/src/js/checkout_form_tracking.js',
            'website_sale_tracking_base/static/src/js/sale_portal_tracking.js',
            'website_sale_tracking_base/static/src/js/website_tracking_form.js',
        ],
    },
    'price': 10.00,
    'currency': 'EUR',
    # ---------------------------
    # LIMITATIONS ON SALE AND USE
    # ---------------------------
    # This module is not sold or distributed separately.
    # It can only be delivered as part of Odoo solutions by Garazd Creation.
    # Prohibited to use this module separately from the solution with which it is supplied.
    # Contact us if you want to use the module for other purposes.
    'support': 'support@garazd.biz',
    'application': True,
    'installable': True,
    'auto_install': False,
}
