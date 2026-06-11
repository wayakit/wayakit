{
    'name': 'PLM Custom',
    'version': '17.0.1.0.1',
    'summary': 'PLM extended: synonym names, dual BoM view, export restrictions',
    'author': 'Your Company',
    'category': 'Manufacturing/PLM',
    'license': 'LGPL-3',
    'depends': [
        'product',
        'mrp',
        'mrp_plm',
    ],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/mrp_bom_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'plm_custom/static/src/js/export_restriction.js',
        ],
    },
    'installable': True,
    'application': False,
}