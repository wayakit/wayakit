{
    'name': 'Website Onepage Checkout',
    'summary': """Consolidates the entire eCommerce checkout process
                  into a single page with accordion-style panels.""",
    'category': 'Website',
    'version': '17.0.1.0.0',
    'author': 'Webkul Software Pvt. Ltd.',
    'license': 'Other proprietary',
    'website': 'https://store.webkul.com/Odoo-Website-Onepage-Checkout.html',
    'depends': [
        'website_sale',
        'website_webkul_addons',
        'payment',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/onepage_checkout_data.xml',
        'views/onepage_checkout_config_views.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_onepage_checkout/static/src/scss/onepage_checkout.scss',
            'website_onepage_checkout/static/src/js/onepage_checkout.js',
        ],
    },
    'images': ['static/description/Banner.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
