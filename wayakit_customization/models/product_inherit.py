from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    duration = fields.Float(string="Duration", default=0)

class ProductTemplateInherit(models.Model):
    """
    Heredamos la PLANTILLA del producto (product.template) para
    añadir el desplegable al 'product.master' y la automatización
    del costo.
    """
    _inherit = 'product.template'

    # 1. ESTE ES EL CAMPO DESPLEGABLE (Many2one)
    # Se conecta a tu modelo 'product.master'.
    master_product_id = fields.Many2one(
        'product.master',
        string="Master Product Record",
        help="Link this product to its register in 'Master Products' to update de cost."
    )

    # 2. ESTA ES LA AUTOMATIZACIÓN
    # Se ejecuta cuando seleccionas algo en el desplegable.
    @api.onchange('master_product_id')
    def _onchange_master_product_id(self):
        """
        Cuando se selecciona un 'Master Product Record',
        copia su costo ('unit_cost_sar') al campo 'Costo'
        de este producto ('standard_price').
        """
        if self.master_product_id:
            # 'standard_price' es el nombre técnico del campo "Costo"
            self.standard_price = self.master_product_id.unit_cost_sar
        else:
            # Si se quita la selección, el costo vuelve a 0
            self.standard_price = 0.0
# --- FIN DEL NUEVO CÓDIGO ---

