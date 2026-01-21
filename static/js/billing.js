let billItems = [];
let currentSelectedItem = null;

function selectItem(id, name, price, element) {
    if (name === 'Ice Cream') {
        const container = document.getElementById('flavor-selection-container');
        container.classList.remove('hidden');
        // Move container after the clicked element's row or just after it in grid
        element.parentNode.insertBefore(container, element.nextSibling);
        document.getElementById('quantity-modal').classList.add('hidden');
        return;
    }

    document.getElementById('flavor-selection-container').classList.add('hidden');
    currentSelectedItem = { id, name, price };
    showQuantityModal(name);
}

function addFlavor() {
    const select = document.getElementById('flavor-select');
    const selectedOption = select.options[select.selectedIndex];

    if (!selectedOption.value) return;

    const name = selectedOption.value;
    const price = parseFloat(selectedOption.getAttribute('data-price'));

    currentSelectedItem = { id: 'flavor-' + name, name: 'Ice Cream (' + name + ')', price: price };
    showQuantityModal(currentSelectedItem.name);

    // Reset select
    select.selectedIndex = 0;
}

function showQuantityModal(name) {
    document.getElementById('current-item-name').innerText = name;
    document.getElementById('quantity-modal').classList.remove('hidden');
    document.getElementById('item-quantity').focus();
    document.getElementById('item-quantity').select();
}

function confirmAddItem() {
    const qty = parseInt(document.getElementById('item-quantity').value);
    if (!qty || qty <= 0) {
        alert("Please enter a valid quantity.");
        return;
    }

    const total = currentSelectedItem.price * qty;

    // Check if item already exists in bill
    const existingIndex = billItems.findIndex(item => item.name === currentSelectedItem.name);
    if (existingIndex > -1) {
        billItems[existingIndex].quantity += qty;
        billItems[existingIndex].total = billItems[existingIndex].quantity * billItems[existingIndex].price;
    } else {
        billItems.push({
            name: currentSelectedItem.name,
            price: currentSelectedItem.price,
            quantity: qty,
            total: total
        });
    }

    updateBillTable();
    document.getElementById('quantity-modal').classList.add('hidden');
    document.getElementById('flavor-selection-container').classList.add('hidden');
}

function updateBillTable() {
    const tbody = document.getElementById('bill-body');
    tbody.innerHTML = '';
    let grandTotal = 0;

    billItems.forEach((item, index) => {
        const row = `
            <tr>
                <td>${item.name}</td>
                <td>${item.quantity}</td>
                <td>₹${item.price.toFixed(2)}</td>
                <td>₹${item.total.toFixed(2)}</td>
                <td><button onclick="removeItem(${index})" class="btn-delete" style="background:none; border:none; cursor:pointer;">&times;</button></td>
            </tr>
        `;
        tbody.innerHTML += row;
        grandTotal += item.total;
    });

    const advance = parseFloat(document.getElementById('bill-advance').value) || 0;
    const discount = parseFloat(document.getElementById('bill-discount').value) || 0;
    const balance = grandTotal - advance - discount;

    document.getElementById('grand-total').innerText = '₹' + grandTotal.toFixed(2);
    document.getElementById('balance-due').innerText = '₹' + (balance < 0 ? 0 : balance).toFixed(2);
}

function removeItem(index) {
    billItems.splice(index, 1);
    updateBillTable();
}

function clearBill() {
    billItems = [];
    document.getElementById('bill-advance').value = '';
    document.getElementById('bill-discount').value = '';
    updateBillTable();
    document.getElementById('bill-success').classList.add('hidden');
}

async function generateBill() {
    if (billItems.length === 0) {
        alert("Please add at least one item to the bill.");
        return;
    }

    const grandTotal = billItems.reduce((sum, item) => sum + item.total, 0);
    const advance = parseFloat(document.getElementById('bill-advance').value) || 0;
    const discount = parseFloat(document.getElementById('bill-discount').value) || 0;
    const balance = grandTotal - advance - discount;
    const location = document.getElementById('bill-location').value;

    const response = await fetch('/generate_bill', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            items: billItems,
            grand_total: grandTotal,
            advance_amount: advance,
            discount_amount: parseFloat(document.getElementById('bill-discount').value) || 0,
            balance_amount: balance,
            location: location
        }),
    });

    const result = await response.json();
    if (result.status === 'success') {
        document.getElementById('bill-success').classList.remove('hidden');
        document.getElementById('view-bill-link').href = result.view_url;
        // Optionally clear bill after success or keep it to show the link
    } else {
        alert("Error generating bill. Please try again.");
    }
}
