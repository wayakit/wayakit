# Copyright © 2018 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License OPL-1 (https://www.odoo.com/documentation/master/legal/licenses.html#odoo-apps).

# flake8: noqa: E501

{
    'name': 'Odoo Facebook Pixel Integration',
    'version': '17.0.2.1.1',
    'category': 'Website',
    'author': 'Garazd Creation',
    'website': 'https://garazd.biz/odoo-website-tracking',
    'license': 'OPL-1',
    'summary': 'Add the Facebook Pixel event "PageView" to all website pages | Facebook Pixel Integration | Meta Pixel Integration | Website activity tracking',
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'live_test_url': 'https://garazd.biz/r/UPR',
    'depends': [
        'website_cookies_consent',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/website_templates.xml',
        'views/website_views.xml',
    ],
    'demo': [
        'demo/website_demo.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_facebook_pixel/static/src/js/cookies_bar.js',
        ],
    },
    'price': 19.00,
    'currency': 'EUR',
    'support': 'support@garazd.biz',
    'application': True,
    'installable': True,
    'auto_install': False,
}
