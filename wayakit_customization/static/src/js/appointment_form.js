/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import "@appointment/js/appointment_form";

publicWidget.registry.appointmentForm.include({
    events: Object.assign({}, publicWidget.registry.appointmentForm.prototype.events, {
        'change select': '_onServiceTypeChange',
        'change input[type="radio"]': '_onServiceTypeChange',
    }),

    start: async function () {
        await this._super(...arguments);
        const durationInput = this.el.querySelector('input[name="duration_str"]') || document.querySelector('input[name="duration_str"]');
        this.originalDurationStr = durationInput ? durationInput.value : "1.0";
        this._updateDurationForDeepCleaning();
    },

    _onServiceTypeChange: function (ev) {
        this._updateDurationForDeepCleaning();
    },

    _isDeepCleaningSelected: function () {
        // Check all selects in the form
        const selects = this.el.querySelectorAll('select');
        for (const select of selects) {
            const selectedOpt = select.selectedOptions[0];
            if (selectedOpt && selectedOpt.textContent.toLowerCase().includes('deep clean')) {
                return true;
            }
        }
        // Check radio buttons
        const checkedRadios = this.el.querySelectorAll('input[type="radio"]:checked');
        for (const radio of checkedRadios) {
            const labelText = radio.closest('label')?.textContent || radio.parentElement?.textContent || "";
            if (labelText.toLowerCase().includes('deep clean')) {
                return true;
            }
        }
        return false;
    },

    _updateDurationForDeepCleaning: function () {
        const durationInput = this.el.querySelector('input[name="duration_str"]') || document.querySelector('input[name="duration_str"]');
        if (!durationInput) {
            return;
        }

        const isDeepClean = this._isDeepCleaningSelected();
        if (isDeepClean) {
            durationInput.value = "2.0";
            this._updateDurationDisplay("2");
        } else {
            durationInput.value = this.originalDurationStr || "1.0";
            this._updateDurationDisplay(this.originalDurationStr || "1.0");
        }
    },

    _updateDurationDisplay: function (durationVal) {
        const detailsCol = document.querySelector('.o_appointment_details_column');
        if (!detailsCol) {
            return;
        }
        const clockIcon = detailsCol.querySelector('.fa-clock-o');
        if (clockIcon && clockIcon.parentElement) {
            const span = clockIcon.parentElement.querySelector('span');
            if (span) {
                const hours = parseFloat(durationVal);
                span.textContent = hours > 1 ? `${hours} hours` : `${hours} hour`;
            }
        }
    },

    _onConfirmAppointment: async function (event) {
        this._updateDurationForDeepCleaning();
        return this._super(...arguments);
    },
});
