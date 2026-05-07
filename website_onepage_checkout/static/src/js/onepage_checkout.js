/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.OnepageCheckout = publicWidget.Widget.extend({
    selector: '#onepage_accordion',
    events: {
        'click .onepage-panel-header': '_onPanelHeaderClick',
        'click .onepage-address-card': '_onAddressCardClick',
        'click .onepage-cart-minus': '_onCartMinus',
        'click .onepage-cart-plus': '_onCartPlus',
        'click .onepage-cart-remove': '_onCartRemove',
        'change select[name="country_id"]': '_onCountryChange',
    },

    init() {
        this._super(...arguments);
        this.rpc = this.bindService("rpc");
        this.completedPanels = new Set();
    },

    start() {
        this._syncPanelClasses();
        return this._super(...arguments);
    },

    // ── Sync CSS classes with panel state on first load ──────────────

    _syncPanelClasses() {
        const panels = this.el.querySelectorAll('.onepage-panel');
        panels.forEach(panel => {
            const content = panel.querySelector('.onepage-panel-content');
            const header = panel.querySelector('.onepage-panel-header');
            const chevron = header ? header.querySelector('.onepage-chevron') : null;
            if (content) content.style.display = '';
            panel.classList.add('panel-open');
            panel.classList.remove('panel-completed', 'panel-pending');
            if (chevron) {
                chevron.classList.remove('fa-chevron-down');
                chevron.classList.add('fa-chevron-up');
            }
        });
    },

    // ── Panel Visibility Logic ───────────────────────────────────────

    _collapsePanel(panel) {
        const content = panel.querySelector('.onepage-panel-content');
        const header = panel.querySelector('.onepage-panel-header');
        const chevron = header ? header.querySelector('.onepage-chevron') : null;

        content.style.display = 'none';
        panel.classList.remove('panel-open');
        if (this.completedPanels.has(panel.id)) {
            panel.classList.add('panel-completed');
        } else {
            panel.classList.add('panel-pending');
        }
        if (chevron) {
            chevron.classList.remove('fa-chevron-up');
            chevron.classList.add('fa-chevron-down');
        }
    },

    _openPanel(contentId) {
        const target = this.el.querySelector('#' + contentId);
        if (!target) return;

        const targetPanel = target.closest('.onepage-panel');
        if (!targetPanel) return;

        target.style.display = '';
        targetPanel.classList.add('panel-open');
        targetPanel.classList.remove('panel-completed', 'panel-pending');
        const header = targetPanel.querySelector('.onepage-panel-header');
        const chevron = header ? header.querySelector('.onepage-chevron') : null;
        if (chevron) {
            chevron.classList.remove('fa-chevron-down');
            chevron.classList.add('fa-chevron-up');
        }
        targetPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    _onPanelHeaderClick(ev) {
        ev.preventDefault();
        const panel = ev.currentTarget.closest('.onepage-panel');
        if (!panel) return;

        if (panel.classList.contains('panel-open')) {
            this._collapsePanel(panel);
            return;
        }

        const targetId = ev.currentTarget.dataset.target;
        if (targetId) {
            this._openPanel(targetId);
        }
    },

    // ── Cart quantity AJAX updates ──────────────────────────────────

    async _updateCartLine(lineEl, newQty) {
        const lineId = parseInt(lineEl.dataset.lineId);
        const productId = parseInt(lineEl.dataset.productId);

        try {
            await this.rpc('/shop/cart/update_json', {
                product_id: productId,
                line_id: lineId,
                set_qty: newQty,
                display: false,
            });

            if (newQty <= 0) {
                lineEl.remove();
                if (!this.el.querySelector('.onepage-cart-line')) {
                    window.location.href = '/shop';
                    return;
                }
            } else {
                lineEl.querySelector('.onepage-cart-qty').textContent = newQty;
            }
            await this._refreshTotals();
        } catch (err) {
            console.error('Cart update failed:', err);
        }
    },

    async _refreshTotals() {
        try {
            const data = await this.rpc('/shop/onepage/get_totals', {});
            if (data.error) return;

            data.lines.forEach(line => {
                const lineEl = this.el.querySelector(`.onepage-cart-line[data-line-id="${line.id}"]`);
                if (lineEl) {
                    const priceEl = lineEl.querySelector('.onepage-cart-price');
                    if (priceEl) priceEl.innerHTML = line.price_html;
                    const qtyEl = lineEl.querySelector('.onepage-cart-qty');
                    if (qtyEl) qtyEl.textContent = line.qty;
                }
            });

            this._updateMonetaryFields('#payment_content', data);
            this._updateMonetaryFields('.o_onepage_summary', data);
        } catch (err) {
            console.error('Totals refresh failed:', err);
        }
    },

    _updateMonetaryFields(containerSel, data) {
        const container = document.querySelector(containerSel);
        if (!container) return;

        container.querySelectorAll('.monetary_field').forEach(el => {
            const row = el.closest('tr');
            if (!row) return;
            const label = row.querySelector('td:first-child');
            if (!label) return;
            const text = label.textContent.trim();
            if (text === 'Subtotal') el.innerHTML = data.subtotal_html;
            else if (text === 'Taxes') el.innerHTML = data.taxes_html;
            else if (text === 'Total') el.innerHTML = data.total_html;
            else if (text === 'Delivery' && data.has_delivery) el.innerHTML = data.delivery_html;
        });
    },

    _onCartMinus(ev) {
        ev.preventDefault();
        const lineEl = ev.currentTarget.closest('.onepage-cart-line');
        const currentQty = parseInt(lineEl.querySelector('.onepage-cart-qty').textContent);
        this._updateCartLine(lineEl, Math.max(0, currentQty - 1));
    },

    _onCartPlus(ev) {
        ev.preventDefault();
        const lineEl = ev.currentTarget.closest('.onepage-cart-line');
        const currentQty = parseInt(lineEl.querySelector('.onepage-cart-qty').textContent);
        this._updateCartLine(lineEl, currentQty + 1);
    },

    _onCartRemove(ev) {
        ev.preventDefault();
        const lineEl = ev.currentTarget.closest('.onepage-cart-line');
        this._updateCartLine(lineEl, 0);
    },

    // ── Dynamic Country/State Logic ──────────────────────────────────

    _onCountryChange: function (ev) {
        const $country = $(ev.currentTarget);
        const countryId = $country.val();
        const $stateSelect = this.$('select[name="state_id"]');

        // Immediate Fix: Clear existing options (except placeholder) so wrong states vanish instantly
        $stateSelect.find('option:not(:first)').remove();

        if (!countryId) {
            $stateSelect.closest('.form-group').addClass('d-none');
            return;
        }

        this.rpc('/shop/country_infos/' + countryId, {
            mode: 'shipping',
        }).then(function (data) {
            if (data.states && data.states.length) {
                data.states.forEach(state => {
                    $stateSelect.append($('<option>', {
                        value: state.id,
                        text: state.name
                    }));
                });
                $stateSelect.closest('.form-group').removeClass('d-none');
            } else {
                $stateSelect.closest('.form-group').addClass('d-none');
            }
        });
    },

    // ── Address selection via AJAX ───────────────────────────────────

    async _onAddressCardClick(ev) {
        ev.preventDefault();
        const card = ev.currentTarget;
        const partnerId = parseInt(card.dataset.partnerId);
        const addressType = card.dataset.addressType;

        if (!partnerId || card.classList.contains('selected')) return;

        try {
            const result = await this.rpc('/shop/onepage/select_address', {
                partner_id: partnerId,
                address_type: addressType,
            });

            if (result.error) return;

            const panel = card.closest('.onepage-panel');
            panel.querySelectorAll('.onepage-address-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
        } catch (err) {
            console.error('Address selection failed:', err);
        }
    },
});

export default publicWidget.registry.OnepageCheckout;