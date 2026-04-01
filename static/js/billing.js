let billItems = [];
let currentSelectedItem = null;

function selectItem(id, name, price, element, description = null) {
    if (!name) { return; }
    // Set state immediately so sub-item selection knows the parent context (and description)
    currentSelectedItem = { id, name, price, description };

    const containers = document.querySelectorAll('.sub-item-container');
    containers.forEach(c => c.classList.add('hidden'));

    name = (name || "").trim();
    const upperName = name.toUpperCase();
    if (upperName === 'ICE CREAM') {
        const container = document.getElementById('flavor-selection-container');
        container.classList.remove('hidden');
        element.parentNode.insertBefore(container, element.nextSibling);
        document.getElementById('quantity-modal').classList.add('hidden');
        return;
    }

    if (upperName === 'FRUITS') {
        const container = document.getElementById('fruit-selection-container');
        container.classList.remove('hidden');
        element.parentNode.insertBefore(container, element.nextSibling);
        document.getElementById('quantity-modal').classList.add('hidden');
        return;
    }

    if (upperName === 'WELCOME DRINKS') {
        const container = document.getElementById('drink-selection-container');
        container.classList.remove('hidden');
        element.parentNode.insertBefore(container, element.nextSibling);
        document.getElementById('quantity-modal').classList.add('hidden');
        return;
    }

    if (upperName === 'BEEDA') {
        const container = document.getElementById('beeda-selection-container');
        container.classList.remove('hidden');
        element.parentNode.insertBefore(container, element.nextSibling);
        document.getElementById('quantity-modal').classList.add('hidden');
        return;
    }

    showQuantityModal(name);
}

function addSubItem(selectId, parentName) {
    const select = document.getElementById(selectId);
    const selectedOption = select.options[select.selectedIndex];

    if (!selectedOption.value) return;

    const name = selectedOption.value;
    const price = parseFloat(selectedOption.getAttribute('data-price'));

    const oldDescription = currentSelectedItem ? currentSelectedItem.description : null;

    currentSelectedItem = {
        id: selectId + '-' + name,
        name: parentName + ' (' + name + ')',
        price: price,
        description: oldDescription
    };
    showQuantityModal(currentSelectedItem.name);

    // Reset select
    select.selectedIndex = 0;
}

function showQuantityModal(name) {
    document.getElementById('current-item-name').innerText = name;

    // Clear or set description
    const descField = document.getElementById('item-description');
    if (descField) {
        descField.value = currentSelectedItem && currentSelectedItem.description ? currentSelectedItem.description : "";
    }

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

    const desc = document.getElementById('item-description').value;

    // Check if item already exists in bill
    const existingIndex = billItems.findIndex(item => item.name.trim() === currentSelectedItem.name.trim());
    if (existingIndex > -1) {
        billItems[existingIndex].quantity += qty;
        billItems[existingIndex].total = billItems[existingIndex].quantity * billItems[existingIndex].price;
        // Also update description if one was provided in the modal
        if (desc) {
            billItems[existingIndex].description = desc;
        }
    } else {
        billItems.push({
            name: currentSelectedItem.name,
            price: parseFloat(currentSelectedItem.price) || 0,
            quantity: qty,
            total: total,
            description: desc || (currentSelectedItem.description || "")
        });
    }

    updateBillTable();
    document.getElementById('quantity-modal').classList.add('hidden');

    // Hide all sub-item containers
    const subContainers = document.querySelectorAll('.sub-item-container');
    subContainers.forEach(c => c.classList.add('hidden'));
}

function updateBillTable() {
    const tbody = document.getElementById('bill-body');
    tbody.innerHTML = '';
    let grandTotal = 0;

    billItems.forEach((item, index) => {
        const row = `
            <tr>
                <td>
                    <div style="font-weight: 600;">${item.name}</div>
                    ${item.description ? `<div style="font-weight: 600; margin-top: 2px;">${item.description}</div>` : ''}
                </td>
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
    const date = document.getElementById('bill-date').value;
    const time = document.getElementById('bill-time').value;

    const payload = {
        items: billItems,
        grand_total: grandTotal,
        advance_amount: advance,
        discount_amount: discount,
        balance_amount: balance,
        party_number: document.getElementById('bill-party-number').value,
        location: location,
        date: date,
        time: time
    };

    try {
        const response = await fetch('/generate_bill', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            let errorMsg = "Server Error while generating bill.";
            try {
                const data = await response.json();
                if (data.message) errorMsg = data.message;
            } catch (e) {
                console.error("Error parsing error response:", e);
            }
            console.error("Server Error Detail:", errorMsg);
            alert(errorMsg + "\n\nCheck console or Vercel logs for more details.");
            return;
        }

        const result = await response.json();
        if (result.status === 'success') {
            document.getElementById('bill-success').classList.remove('hidden');
            document.getElementById('view-bill-link').href = result.view_url;
        } else {
            alert("Error: " + (result.message || "Unknown error occurred"));
        }
    } catch (e) {
        console.error("JS Error:", e);
        alert("An error occurred in the browser. Check console for details.");
    }
}
