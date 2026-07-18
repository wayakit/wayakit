{
    'name': 'Quality Custom',
    'version': '17.0.1.0.0',
    'summary': 'Quality extended: tolerance range on worksheet-type control points',
    'author': 'Your Company',
    'category': 'Manufacturing/Quality',
    'license': 'LGPL-3',
    'depends': [
        'quality_control_worksheet',
    ],
    'data': [
        'views/quality_point_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'quality_custom/static/src/ph_slider/ph_slider.js',
            'quality_custom/static/src/ph_slider/ph_slider.xml',
        ],
    },
    'installable': True,
    'application': False,
}
