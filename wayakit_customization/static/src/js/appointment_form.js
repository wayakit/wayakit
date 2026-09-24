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
        this._updateDurationForCarpet();
        this._updateKitchen();
    },

    _onServiceTypeChange: function (ev) {
        this._updateDurationForDeepCleaning();
        this._updateDurationForCarpet();
        this._updateKitchen();
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
        this._updateDurationForCarpet();
        this._updateKitchen();
        return this._super(...arguments);
    },

    _isCurtainFurnitureAppointment: function () {
        const detailsHeader = document.querySelector('.o_appointment_details_type h5') ||
                              document.querySelector('.o_appointment_details_column h5') ||
                              document.querySelector('.o_appointment_details_type');
        if (detailsHeader) {
            const headerText = detailsHeader.textContent.toLowerCase();
            if (headerText.includes('curtain') && headerText.includes('furniture')) {
                return true;
            }
        }
        const formText = (this.el ? this.el.textContent : '').toLowerCase();
        if (formText.includes('curtain') || (formText.includes('carpet') && formText.includes('sofa'))) {
            return true;
        }
        return false;
    },

    _isCarpetSelected: function () {
        // 1. Check all selects in the form
        const selects = this.el.querySelectorAll('select');
        for (const select of selects) {
            const selectedOpt = select.selectedOptions ? select.selectedOptions[0] : select.options[select.selectedIndex];
            if (!selectedOpt) {
                continue;
            }
            const optText = selectedOpt.textContent.trim();
            const optLower = optText.toLowerCase();

            // Option itself mentions carpet
            if (optLower.includes('carpet')) {
                return true;
            }

            // Question / label mentions carpet and selected quantity > 0
            const row = select.closest('.row');
            const label = (select.name ? this.el.querySelector(`label[for="${select.name}"]`) : null) ||
                          (row ? row.querySelector('label') : null);
            const labelText = (label ? label.textContent : '').toLowerCase();

            if (labelText.includes('carpet')) {
                const qty = parseInt(optText, 10);
                if (!isNaN(qty)) {
                    if (qty > 0) {
                        return true;
                    }
                } else if (optText && !['0', 'none', 'no', 'false'].includes(optLower)) {
                    return true;
                }
            }
        }

        // 2. Check radio buttons
        const checkedRadios = this.el.querySelectorAll('input[type="radio"]:checked');
        for (const radio of checkedRadios) {
            const labelText = (radio.closest('label')?.textContent || radio.parentElement?.textContent || "").toLowerCase();
            const row = radio.closest('.row');
            const questionLabel = (row?.querySelector('label.col-form-label')?.textContent || "").toLowerCase();

            if (labelText.includes('carpet')) {
                if (!['0', 'none', 'no', 'false'].includes(labelText.trim())) {
                    return true;
                }
            }
            if (questionLabel.includes('carpet')) {
                const qty = parseInt(labelText, 10);
                if (!isNaN(qty)) {
                    if (qty > 0) {
                        return true;
                    }
                } else if (!['0', 'none', 'no', 'false'].includes(labelText.trim())) {
                    return true;
                }
            }
        }

        // 3. Check checkboxes
        const checkedCheckboxes = this.el.querySelectorAll('input[type="checkbox"]:checked');
        for (const cb of checkedCheckboxes) {
            const labelText = (cb.closest('label')?.textContent || cb.parentElement?.textContent || "").toLowerCase();
            const row = cb.closest('.row');
            const questionLabel = (row?.querySelector('label.col-form-label')?.textContent || "").toLowerCase();

            if (labelText.includes('carpet') || questionLabel.includes('carpet')) {
                return true;
            }
        }

        return false;
    },

    _kitchenGroup: function (questionName) {
        const name = (questionName || '').toLowerCase();
        if (!name.includes('kitchen')) {
            return null;
        }
        return name.includes('oasis')
            ? { hours: 1.5, label: '1 h 30 min', areas: ['oasis', 'harbor'] }
            : { hours: 2.0, label: '2 hours', areas: ['garden', 'island', 'palm', 'nhc'] };
    },

    _selectedEnglishAnswer: function (select) {
        const opt = select.selectedOptions ? select.selectedOptions[0] : null;
        return ((opt && (opt.dataset.wkAnswer || opt.textContent)) || '').trim().toLowerCase();
    },

    // Kitchen Steam Deep Cleaning: hide the kitchen question that does not
    // match the chosen Area and show the visit length of the one picked.
    // Reads the English names from data-wk-* (appointment_kitchen_templates.xml)
    // so it also works on the Arabic form. The server re-checks both.
    _updateKitchen: function () {
        const rows = this.el.querySelectorAll('[data-wk-question]');
        let area = '';
        for (const row of rows) {
            const select = row.querySelector('select');
            if (select && row.dataset.wkQuestion.trim().toLowerCase() === 'area') {
                area = this._selectedEnglishAnswer(select);
            }
        }
        let picked = null;
        for (const row of rows) {
            const group = this._kitchenGroup(row.dataset.wkQuestion);
            const select = row.querySelector('select');
            if (!group || !select) {
                continue;
            }
            const allowed = !area || group.areas.includes(area);
            row.classList.toggle('d-none', !allowed);
            if (!allowed) {
                const zero = [...select.options].find((opt) => opt.textContent.trim() === '0');
                if (zero) {
                    select.value = zero.value;
                }
            }
            if (allowed && parseInt(this._selectedEnglishAnswer(select), 10) > 0 &&
                    (!picked || group.hours > picked.hours)) {
                picked = group;
            }
        }
        if (!picked) {
            return;
        }
        const durationInput = this.el.querySelector('input[name="duration_str"]') || document.querySelector('input[name="duration_str"]');
        if (durationInput) {
            durationInput.value = String(picked.hours);
        }
        const detailsCol = document.querySelector('.o_appointment_details_column');
        const clockIcon = detailsCol ? detailsCol.querySelector('.fa-clock-o') : null;
        const span = clockIcon && clockIcon.parentElement ? clockIcon.parentElement.querySelector('span') : null;
        if (span) {
            span.textContent = picked.label;
        }
    },

    _updateDurationForCarpet: function () {
        if (!this._isCurtainFurnitureAppointment()) {
            return;
        }

        const durationInput = this.el.querySelector('input[name="duration_str"]') || document.querySelector('input[name="duration_str"]');
        if (!durationInput) {
            return;
        }

        const detailsCol = document.querySelector('.o_appointment_details_column');
        const clockIcon = detailsCol ? detailsCol.querySelector('.fa-clock-o') : null;
        const span = clockIcon && clockIcon.parentElement ? clockIcon.parentElement.querySelector('span') : null;

        const isCarpet = this._isCarpetSelected();
        if (isCarpet) {
            durationInput.value = "0.5";
            if (span) {
                span.textContent = "30 min";
            }
        } else {
            durationInput.value = this.originalDurationStr || "2.0";
            if (span) {
                const hours = parseFloat(this.originalDurationStr || "2.0");
                span.textContent = hours > 1 ? `${hours} hours` : `${hours} hour`;
            }
        }
    },
});
