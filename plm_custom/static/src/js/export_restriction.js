/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

// UI layer only. The real protection is server-side: plm.mask.mixin.export_data
// blocks the ORM path (including a direct call_kw RPC) and the controllers in
// controllers/export.py answer 403 on /web/export/* and /web/pivot/export_xlsx.
// These patches only spare the user a download that would fail anyway.

const FORMULA_MODELS = ["mrp.bom", "mrp.bom.line"];
const PRODUCT_MODELS = ["product.template", "product.product"];

const BOM_MESSAGE =
    "PLM Restriction: Standard users are not allowed to export Bills of Materials.";
const PRODUCT_MESSAGE =
    "PLM Restriction: You cannot export PLM Components or products that contain a Bill of Materials.";
const FORMULA_MESSAGE =
    "PLM Restriction: Standard users are not allowed to export formula data.";

function usePlmGroups(component) {
    component.notification = useService("notification");
    component.userService = useService("user");
    component.isPlmStandard = false;
    component.isPlmConfidential = false;

    onWillStart(async () => {
        component.isPlmStandard = await component.userService.hasGroup(
            "plm_custom.group_plm_standard"
        );
        component.isPlmConfidential = await component.userService.hasGroup(
            "plm_custom.group_plm_confidential"
        );
    });
}

function isPlmRestricted(component) {
    // Confidential implies Standard, hence the second half.
    return component.isPlmStandard && !component.isPlmConfidential;
}

function blockExport(component, message) {
    component.notification.add(message, {
        type: "danger",
        title: "Export Blocked",
    });
}

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        usePlmGroups(this);
    },

    /**
     * Patched on downloadExport rather than onExportData: the "Export All" cog
     * item fires onDirectExportData, which calls downloadExport directly and
     * never goes through the export dialog. Both paths converge here.
     */
    async downloadExport(fields, import_compat, format) {
        if (await this._plmExportBlocked()) {
            return;
        }
        return super.downloadExport(...arguments);
    },

    async _plmExportBlocked() {
        if (!isPlmRestricted(this)) {
            return false;
        }
        const resModel = this.props.resModel;

        if (FORMULA_MODELS.includes(resModel)) {
            blockExport(this, BOM_MESSAGE);
            return true;
        }

        if (PRODUCT_MODELS.includes(resModel)) {
            const restricted = [
                "|",
                ["is_plm_component", "=", true],
                ["bom_ids", "!=", false],
            ];
            const selected = this.model.root.selection;
            const domain =
                selected && selected.length
                    ? [["id", "in", selected.map((r) => r.resId)], ...restricted]
                    : [...(this.model.root.domain || []), ...restricted];
            if ((await this.orm.searchCount(resModel, domain)) > 0) {
                blockExport(this, PRODUCT_MESSAGE);
                return true;
            }
        }

        return false;
    },
});

// The pivot download lives on the RENDERER, not the controller, and posts to
// /web/pivot/export_xlsx -- a wholly separate pipeline from /web/export/*.
// The graph view needs no patch: it has no export path in Odoo 17.
patch(PivotRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        usePlmGroups(this);
    },

    onDownloadButtonClicked() {
        if (isPlmRestricted(this)) {
            const resModel = this.model.metaData.resModel;
            if (
                FORMULA_MODELS.includes(resModel) ||
                PRODUCT_MODELS.includes(resModel)
            ) {
                blockExport(this, FORMULA_MESSAGE);
                return;
            }
        }
        return super.onDownloadButtonClicked(...arguments);
    },
});
