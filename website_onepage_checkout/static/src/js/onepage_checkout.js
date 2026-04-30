/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.OnepageCheckout = publicWidget.Widget.extend({
    selector: '#onepage_accordion',
    events: {
        'click .onepage-panel-header': '_onPanelHeaderClick',
        // 'click .onepage-continue': '_onContinueClick',  // Removed: all panels open by default
        'click .onepage-address-card': '_onAddressCardClick',
        'click .onepage-cart-minus': '_onCartMinus',
        'click .onepage-cart-plus': '_onCartPlus',
        'click .onepage-cart-remove': '_onCartRemove',
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
        // All panels are always open — no accordion gating
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

        // Old accordion-style sync (commented out)
        // let foundOpen = false;
        // panels.forEach(panel => {
        //     const content = panel.querySelector('.onepage-panel-content');
        //     if (content && content.style.display !== 'none') {
        //         panel.classList.add('panel-open');
        //         panel.classList.remove('panel-completed', 'panel-pending');
        //         foundOpen = true;
        //     } else if (!foundOpen) {
        //         panel.classList.remove('panel-open', 'panel-pending');
        //     } else {
        //         panel.classList.add('panel-pending');
        //         panel.classList.remove('panel-open', 'panel-completed');
        //     }
        // });
    },

    // ── Collapse the currently open panel ────────────────────────────

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

    // ── Open a panel, keep completed panels green ───────────────────

    _openPanel(contentId) {
        const target = this.el.querySelector('#' + contentId);
        if (!target) return;

        const targetPanel = target.closest('.onepage-panel');
        if (!targetPanel) return;

        // Only open the target panel — do not collapse others
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

        // Old accordion logic that closed other panels (commented out)
        // const panels = [...this.el.querySelectorAll('.onepage-panel')];
        // panels.forEach(panel => {
        //     const content = panel.querySelector('.onepage-panel-content');
        //     const header = panel.querySelector('.onepage-panel-header');
        //     const chevron = header ? header.querySelector('.onepage-chevron') : null;
        //     if (panel === targetPanel) {
        //         content.style.display = '';
        //         panel.classList.add('panel-open');
        //         panel.classList.remove('panel-completed', 'panel-pending');
        //         if (chevron) { chevron.classList.remove('fa-chevron-down'); chevron.classList.add('fa-chevron-up'); }
        //     } else {
        //         content.style.display = 'none';
        //         if (chevron) { chevron.classList.remove('fa-chevron-up'); chevron.classList.add('fa-chevron-down'); }
        //         if (this.completedPanels.has(panel.id)) {
        //             panel.classList.add('panel-completed'); panel.classList.remove('panel-open', 'panel-pending');
        //         } else {
        //             panel.classList.add('panel-pending'); panel.classList.remove('panel-open', 'panel-completed');
        //         }
        //     }
        // });
    },

    _onPanelHeaderClick(ev) {
        ev.preventDefault();
        const panel = ev.currentTarget.closest('.onepage-panel');
        if (!panel) return;

        // Any panel can be freely toggled — no gating on completedPanels
        if (panel.classList.contains('panel-open')) {
            this._collapsePanel(panel);
            return;
        }

        const targetId = ev.currentTarget.dataset.target;
        if (targetId) {
            this._openPanel(targetId);
        }

        // Old gated accordion logic (commented out)
        // if (this.completedPanels.has(panel.id)) {
        //     const targetId = ev.currentTarget.dataset.target;
        //     if (targetId) { this._openPanel(targetId); }
        //     return;
        // }
        // const panels = [...this.el.querySelectorAll('.onepage-panel')];
        // const isLastPanel = panel === panels[panels.length - 1];
        // const allPreviousCompleted = panels.slice(0, -1).every(p => this.completedPanels.has(p.id));
        // if (isLastPanel && allPreviousCompleted) {
        //     const targetId = ev.currentTarget.dataset.target;
        //     if (targetId) { this._openPanel(targetId); }
        // }
    },

    // _onContinueClick removed: all panels open by default, no step-by-step navigation needed
    // _onContinueClick(ev) {
    //     ev.preventDefault();
    //     const currentPanel = ev.currentTarget.closest('.onepage-panel');
    //     if (currentPanel) {
    //         this.completedPanels.add(currentPanel.id);
    //     }
    //     const nextPanel = ev.currentTarget.dataset.next;
    //     if (nextPanel) {
    //         this._openPanel(nextPanel);
    //     }
    // },

    // ── Cart quantity AJAX updates (no page reload) ─────────────────

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

            // Fetch fresh formatted totals from server
            await this._refreshTotals();

        } catch (err) {
            console.error('Cart update failed:', err);
        }
    },

    async _refreshTotals() {
        try {
            const data = await this.rpc('/shop/onepage/get_totals', {});
            if (data.error) return;

            // Update line prices in payment panel
            data.lines.forEach(line => {
                const lineEl = this.el.querySelector(
                    `.onepage-cart-line[data-line-id="${line.id}"]`
                );
                if (lineEl) {
                    const priceEl = lineEl.querySelector('.onepage-cart-price');
                    if (priceEl) priceEl.innerHTML = line.price_html;
                    const qtyEl = lineEl.querySelector('.onepage-cart-qty');
                    if (qtyEl) qtyEl.textContent = line.qty;
                }
            });

            // Update totals in payment panel
            this._updateMonetaryFields(
                '#payment_content', data, true
            );
            // Update totals in sidebar
            this._updateMonetaryFields(
                '.o_onepage_summary', data, false
            );

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
            if (text === 'Subtotal') {
                el.innerHTML = data.subtotal_html;
            } else if (text === 'Taxes') {
                el.innerHTML = data.taxes_html;
            } else if (text === 'Total') {
                el.innerHTML = data.total_html;
            } else if (text === 'Delivery' && data.has_delivery) {
                el.innerHTML = data.delivery_html;
            }
        });
    },

    _onCartMinus(ev) {
        ev.preventDefault();
        const lineEl = ev.currentTarget.closest('.onepage-cart-line');
        const currentQty = parseInt(
            lineEl.querySelector('.onepage-cart-qty').textContent
        );
        this._updateCartLine(lineEl, Math.max(0, currentQty - 1));
    },

    _onCartPlus(ev) {
        ev.preventDefault();
        const lineEl = ev.currentTarget.closest('.onepage-cart-line');
        const currentQty = parseInt(
            lineEl.querySelector('.onepage-cart-qty').textContent
        );
        this._updateCartLine(lineEl, currentQty + 1);
    },

    _onCartRemove(ev) {
        ev.preventDefault();
        const lineEl = ev.currentTarget.closest('.onepage-cart-line');
        this._updateCartLine(lineEl, 0);
    },

    // ── Address selection via AJAX ───────────────────────────────────

    async _onAddressCardClick(ev) {
        ev.preventDefault();
        const card = ev.currentTarget;
        const partnerId = parseInt(card.dataset.partnerId);
        const addressType = card.dataset.addressType;

        if (!partnerId || card.classList.contains('selected')) {
            return;
        }

        try {
            const result = await this.rpc('/shop/onepage/select_address', {
                partner_id: partnerId,
                address_type: addressType,
            });

            if (result.error) {
                console.error(result.error);
                return;
            }

            const panel = card.closest('.onepage-panel');
            panel.querySelectorAll('.onepage-address-card').forEach(c => {
                c.classList.remove('selected');
            });
            card.classList.add('selected');

        } catch (err) {
            console.error('Address selection failed:', err);
        }
    },
});

export default publicWidget.registry.OnepageCheckout;
