/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);

        // Importamos los servicios necesarios de Odoo
        this.userService = useService("user");
        this.notification = useService("notification");
        this.orm = useService("orm");

        this.isPlmStandard = false;
        this.isPlmConfidential = false;

        // Verificamos los grupos del usuario antes de que el componente se monte
        onWillStart(async () => {
            this.isPlmStandard = await this.userService.hasGroup("plm_custom.group_plm_standard");
            this.isPlmConfidential = await this.userService.hasGroup("plm_custom.group_plm_confidential");
        });
    },

    async onExportData() {
        // Si el usuario es Confidential, tiene acceso total, pasa directo a la exportación nativa
        if (this.isPlmConfidential) {
            return super.onExportData(...arguments);
        }

        // Si es usuario Standard, aplicamos las restricciones
        if (this.isPlmStandard) {

            // 1. Restricción en BoM: Bloqueo total
            if (this.props.resModel === "mrp.bom") {
                this.notification.add(
                    "PLM Restriction: Standard users are not allowed to export Bills of Materials.",
                    { type: "danger", title: "Export Blocked" }
                );
                return; // Detenemos la función aquí
            }

            // 2. Restricción en Productos: Bloqueo si hay categoría PLM Component O si tienen un BoM
            if (this.props.resModel === "product.template" || this.props.resModel === "product.product") {
                const selectedRecords = this.model.root.selection;
                let hasRestrictedProduct = false;

                if (selectedRecords && selectedRecords.length > 0) {
                    // Si el usuario seleccionó casillas específicas
                    const selectedIds = selectedRecords.map(r => r.resId);
                    const count = await this.orm.searchCount(this.props.resModel, [
                        ['id', 'in', selectedIds],
                        '|',
                        ['is_plm_component', '=', true],
                        ['bom_ids', '!=', false]
                    ]);
                    hasRestrictedProduct = count > 0;
                } else {
                    // Si no seleccionó casillas e intenta exportar basándose en el filtro actual
                    const domain = this.model.root.domain || [];
                    const count = await this.orm.searchCount(this.props.resModel, [
                        ...domain,
                        '|',
                        ['is_plm_component', '=', true],
                        ['bom_ids', '!=', false]
                    ]);
                    hasRestrictedProduct = count > 0;
                }

                if (hasRestrictedProduct) {
                    this.notification.add(
                        "PLM Restriction: You cannot export PLM Components or products that contain a Bill of Materials.",
                        { type: "danger", title: "Export Blocked" }
                    );
                    return; // Detenemos la función aquí
                }
            }
        }

        // Si es otro modelo, o si son productos normales sin BoM, permitimos la exportación
        return super.onExportData(...arguments);
    }
});