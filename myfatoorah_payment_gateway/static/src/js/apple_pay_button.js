/** @odoo-module **/

function insertApplePayButton() {
    const paymentOption = document.querySelector('li[name="o_payment_option"]');
    if (!paymentOption) {
        return;
    }

    if (document.getElementById('mf_apple_pay_wrapper')) {
        return;
    }

    const li = document.createElement('li');
    li.id = 'mf_apple_pay_wrapper';
    li.className = 'list-group-item py-3';

    li.innerHTML = `
        <button type="button"
                id="mf_apple_pay_btn"
                class="btn btn-dark w-100 d-flex align-items-center justify-content-center"
                style="min-height:48px; border-radius:6px; font-weight:600;">
            <span style="font-size:18px; line-height:1;"></span>
            <span class="ms-2">Pay with Apple Pay</span>
        </button>
    `;

    paymentOption.parentNode.insertBefore(li, paymentOption);
}

function waitForPaymentOptions() {
    insertApplePayButton();

    const observer = new MutationObserver(() => {
        insertApplePayButton();
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });
}

document.addEventListener('DOMContentLoaded', waitForPaymentOptions);