/** @odoo-module **/
// pH input as a 0-14 range slider. Odoo has no native slider widget for
// numeric fields, so register a tiny OWL field widget. Bound to the float
// field x_studio_ph_level; used from the worksheet arch as widget="ph_slider".
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

export class PhSlider extends Component {
    static template = "quality_custom.PhSlider";
    static props = {
        ...standardFieldProps,
        min: { type: Number, optional: true },
        max: { type: Number, optional: true },
        step: { type: Number, optional: true },
    };

    get value() {
        return this.props.record.data[this.props.name] ?? 0;
    }

    // input (not change) so the Pass/Fail badge recomputes live while dragging.
    onInput(ev) {
        this.props.record.update({ [this.props.name]: parseFloat(ev.target.value) });
    }
}

export const phSlider = {
    component: PhSlider,
    displayName: "pH Slider",
    supportedTypes: ["float"],
    extractProps: ({ options }) => ({
        min: options.min ?? 0,
        max: options.max ?? 14,
        step: options.step ?? 0.1,
    }),
};

registry.category("fields").add("ph_slider", phSlider);