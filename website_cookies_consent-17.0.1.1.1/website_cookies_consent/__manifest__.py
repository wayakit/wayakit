# Copyright © 2024 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License OPL-1 (https://www.odoo.com/documentation/master/legal/licenses.html#odoo-apps).

{
    'name': 'Odoo Cookies Consent Management',
    'version': '17.0.1.1.1',
    'category': 'Website',
    'author': 'Garazd Creation',
    'website': 'https://garazd.biz/shop',
    'license': 'OPL-1',
    'summary': 'Cookies Consent Management Base',
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'live_test_url': 'https://garazd.biz/r/4IZ',
    'depends': [
        'website',
    ],
    'data': [
        'views/website_views.xml',
        'views/res_config_settings_views.xml',
        'views/website_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_cookies_consent/static/src/js/cookies_consent.js',
        ],
    },
    'price': 1.00,
    'currency': 'EUR',
    # ---------------------------
    # LIMITATIONS ON SALE AND USE
    # ---------------------------
    # This module is not sold or distributed separately.
    # It can only be delivered as part of Odoo solutions by Garazd Creation.
    # Prohibited to use this module separately from the solution with which it is supplied.
    # Contact us if you want to use the module for other purposes.
    'support': 'support@garazd.biz',
    'application': False,
    'installable': True,
    'auto_install': False,
}
