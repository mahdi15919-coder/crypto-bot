const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const API_BASE = "https://crypto-bot-api-atmh.onrender.com";
const ADMIN_ID = 5869677184;

const welcomeText = document.getElementById("welcomeText");
const userBadge = document.getElementById("userBadge");
const panelTitle = document.getElementById("panelTitle");
const panelBody = document.getElementById("panelBody");

const showPricesBtn = document.getElementById("showPricesBtn");
const buySellBtn = document.getElementById("buySellBtn");
const showOrdersBtn = document.getElementById("showOrdersBtn");
const adminPanelBtn = document.getElementById("adminPanelBtn");
const homeBtn = document.getElementById("homeBtn");

let orderData = {};

function currentUserId() {
  return tg?.initDataUnsafe?.user?.id;
}

function currentUserName() {
  return tg?.initDataUnsafe?.user?.first_name || tg?.initDataUnsafe?.user?.username || "دوست عزیز";
}

function isAdmin() {
  return Number(currentUserId()) === Number(ADMIN_ID);
}

function setPanel(title, html) {
  panelTitle.textContent = title;
  panelBody.innerHTML = html;
}

function formatIrr(value) {
  return Math.round(value).toLocaleString("fa-IR");
}

function copyText(text) {
  navigator.clipboard.writeText(text)
    .then(() => alert("کپی شد"))
    .catch(() => alert("کپی نشد"));
}

async function getJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "خطا");
  return data;
}

async function postJSON(path, payload) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "خطا");
  return data;
}

function initUi() {
  welcomeText.textContent = `سلام ${currentUserName()}، پنل آماده‌ست.`;
  userBadge.textContent = isAdmin() ? "ADMIN" : "USER";
  if (!isAdmin()) adminPanelBtn.classList.add("hidden");
}

async function loadHome() {
  try {
    const data = await getJSON("/summary");
    setPanel(
      "داشبورد",
      `
      <div class="stat-grid">
        <div class="stat-card">
          <div class="label">قیمت فروش تتر</div>
          <div class="value">${formatIrr(data.usdt_prices.sell_to_user)} ریال</div>
        </div>
        <div class="stat-card">
          <div class="label">قیمت خرید تتر</div>
          <div class="value">${formatIrr(data.usdt_prices.buy_from_user)} ریال</div>
        </div>
        <div class="stat-card">
          <div class="label">تعداد بانک‌ها</div>
          <div class="value">${data.bank_count}</div>
        </div>
        <div class="stat-card">
          <div class="label">تعداد ولت‌ها</div>
          <div class="value">${data.wallet_count}</div>
        </div>
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
}

homeBtn.addEventListener("click", loadHome);

showPricesBtn.addEventListener("click", async () => {
  try {
    const data = await getJSON("/summary");
    setPanel(
      "قیمت تتر",
      `
      <div class="list-item">
        🟢 فروش به شما: <strong>${formatIrr(data.usdt_prices.sell_to_user)}</strong> ریال
        <br>
        🔴 خرید از شما: <strong>${formatIrr(data.usdt_prices.buy_from_user)}</strong> ریال
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
});

buySellBtn.addEventListener("click", () => {
  orderData = {};
  setPanel(
    "نوع معامله",
    `
    <div class="list-item">
      <div class="grid-actions">
        <button class="card small green" onclick="selectSide('buy')">🟢 خرید</button>
        <button class="card small red" onclick="selectSide('sell')">🔴 فروش</button>
      </div>
    </div>
    `
  );
});

window.selectSide = function(side) {
  orderData.side = side;
  setPanel(
    "انتخاب ارز",
    `
    <div class="list-item">
      <div class="grid-actions">
        <button class="card small" onclick="selectAsset('USDT')">💵 USDT</button>
        <button class="card small" onclick="selectAsset('TRX')">⚡ TRX</button>
        <button class="card small" onclick="selectAsset('TON')">🌐 TON</button>
        <button class="card small" onclick="selectAsset('BNB')">🟡 BNB</button>
      </div>
    </div>
    `
  );
};

window.selectAsset = async function(asset) {
  orderData.asset_code = asset;
  try {
    const data = await getJSON(`/networks?asset_code=${asset}`);
    const buttons = data.networks
      .map(n => `<button class="card small" onclick="selectNetwork('${n}')">${n}</button>`)
      .join("");

    setPanel("انتخاب شبکه", `<div class="list-item"><div class="grid-actions">${buttons}</div></div>`);
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.selectNetwork = function(network) {
  orderData.network = network;
  setPanel(
    "مقدار",
    `
    <div class="list-item">
      <div class="form-group">
        <label>مقدار</label>
        <input id="amountInput" type="number" step="any" placeholder="مثلاً 10">
      </div>
      <button class="card small orange" onclick="getQuote()">ادامه</button>
    </div>
    `
  );
};

window.getQuote = async function() {
  const amount = parseFloat(document.getElementById("amountInput").value);
  if (!amount || amount <= 0) {
    alert("مقدار معتبر نیست");
    return;
  }

  orderData.amount = amount;

  try {
    const quote = await postJSON("/quote", {
      side: orderData.side,
      asset_code: orderData.asset_code,
      network: orderData.network,
      amount: orderData.amount
    });

    setPanel(
      "پیش‌نمایش سفارش",
      `
      <div class="list-item">
        <strong>نوع:</strong> ${quote.side === "buy" ? "خرید" : "فروش"}<br>
        <strong>ارز:</strong> ${quote.asset_code}<br>
        <strong>شبکه:</strong> ${quote.network}<br>
        <strong>مقدار:</strong> ${quote.amount}<br>
        <strong>قیمت هر واحد:</strong> ${formatIrr(quote.unit_price_irr)} ریال<br>
        <strong>کارمزد:</strong> ${quote.fee_amount} ${quote.fee_asset}<br>
        <strong>مبلغ نهایی:</strong> ${formatIrr(quote.total_irr)} ریال
      </div>

      <div class="list-item">
        <div class="form-group">
          <label>آدرس مقصد / مبدا</label>
          <input id="walletAddressInput" type="text" placeholder="آدرس را وارد کن">
        </div>
        <button class="card small orange" onclick="submitOrder()">ثبت سفارش</button>
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.submitOrder = async function() {
  const walletAddress = document.getElementById("walletAddressInput").value.trim();
  const userId = currentUserId();

  if (!walletAddress) {
    alert("آدرس را وارد کن");
    return;
  }
  if (!userId) {
    alert("شناسه کاربر پیدا نشد");
    return;
  }

  try {
    const data = await postJSON("/create-order", {
      user_id: userId,
      side: orderData.side,
      asset_code: orderData.asset_code,
      network: orderData.network,
      amount: orderData.amount,
      wallet_address: walletAddress
    });

    setPanel(
      "سفارش ثبت شد",
      `
      <div class="list-item">
        ✅ سفارش ${data.order.order_id} ثبت شد.
        <br><br>
        ⏳ منتظر تأیید ادمین باشید.
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

showOrdersBtn.addEventListener("click", loadUserOrders);

async function loadUserOrders() {
  try {
    const userId = currentUserId();
    const orders = await getJSON(`/orders?user_id=${userId}`);

    if (!orders.length) {
      setPanel("سفارش‌های من", "هنوز سفارشی نداری");
      return;
    }

    const html = orders.slice().reverse().map(o => {
      let actionHtml = "";

      if (o.status === "pending_admin") {
        actionHtml = "⏳ منتظر تأیید ادمین";
      } else if (o.status === "waiting_bank") {
        actionHtml = `<button class="card small" onclick="showBankSelection('${o.order_id}')">🏦 انتخاب بانک</button>`;
      } else if (o.status === "waiting_receipt") {
        actionHtml = `
          <div class="form-group"><label>آپلود رسید</label><input id="file-${o.order_id}" type="file" accept="image/*"></div>
          <button class="card small green" onclick="uploadReceipt('${o.order_id}')">📤 ارسال رسید</button>
        `;
      } else if (o.status === "receipt_submitted") {
        actionHtml = `📨 رسید ثبت شد، منتظر بررسی ادمین`;
      } else if (o.status === "wallet_ready" || o.status === "waiting_txid") {
        actionHtml = `
          <button class="card small" onclick="showOrderWallet('${o.order_id}')">👛 نمایش ولت</button>
          <div class="form-group" style="margin-top:12px;"><label>TXID</label><input id="tx-${o.order_id}" type="text" placeholder="TXID"></div>
          <button class="card small orange" onclick="submitTx('${o.order_id}')">🔗 ثبت TXID</button>
        `;
      } else if (o.status === "txid_submitted") {
        actionHtml = `📨 TXID ثبت شد، منتظر بررسی ادمین`;
      } else if (o.status === "paid") {
        actionHtml = o.side === "buy" ? "💰 پرداخت تأیید شد، منتظر ارسال ارز" : "💰 واریز شما تأیید شد، منتظر پرداخت ریالی";
      } else if (o.status === "sent") {
        actionHtml = "🚀 ارز ارسال شد";
      } else if (o.status === "done") {
        actionHtml = "✅ سفارش تکمیل شد";
      } else if (o.status === "rejected") {
        actionHtml = "❌ سفارش رد شد";
      }

      return `
        <div class="list-item">
          <strong>کد سفارش:</strong> ${o.order_id}<br>
          <strong>نوع:</strong> ${o.side === "buy" ? "خرید" : "فروش"}<br>
          <strong>ارز:</strong> ${o.asset_code}<br>
          <strong>شبکه:</strong> ${o.network}<br>
          <strong>مقدار:</strong> ${o.amount}<br>
          <strong>مبلغ:</strong> ${formatIrr(o.total_irr)} ریال<br>
          <strong>وضعیت:</strong> ${o.status}<br>
          ${o.receipt_url ? `<strong>رسید:</strong> <a href="${API_BASE}${o.receipt_url}" target="_blank">مشاهده</a><br>` : ""}
          ${o.txid ? `<strong>TXID:</strong> ${o.txid}<br>` : ""}
          <br>
          ${actionHtml}
        </div>
      `;
    }).join("");

    setPanel("سفارش‌های من", html);
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
}

window.showBankSelection = async function(orderId) {
  try {
    const banks = await getJSON("/banks");
    if (!banks.length) {
      setPanel("انتخاب بانک", "هیچ حساب بانکی ثبت نشده");
      return;
    }

    const html = banks.map(
      b => `
      <div class="list-item">
        <strong>${b.bank_name}</strong> - ${b.owner_name}<br><br>
        <button class="card small" onclick="selectBankForOrder('${orderId}', '${b.id}')">انتخاب این حساب</button>
      </div>
      `
    ).join("");

    setPanel("انتخاب بانک", html);
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.selectBankForOrder = async function(orderId, bankId) {
  try {
    const data = await postJSON(`/order/${orderId}/select-bank`, {
      user_id: currentUserId(),
      bank_id: bankId
    });

    const bank = data.bank;
    setPanel(
      "اطلاعات بانکی",
      `
      <div class="list-item">
        <strong>بانک:</strong> ${bank.bank_name}<br>
        <strong>صاحب حساب:</strong> ${bank.owner_name}<br>
        <strong>شماره کارت:</strong> ${bank.card_number}<br>
        <strong>شماره حساب:</strong> ${bank.account_number}<br>
        <strong>شبا:</strong> ${bank.sheba}<br><br>
        <div class="grid-actions">
          <button class="card small" onclick="copyText('${bank.card_number}')">کپی کارت</button>
          <button class="card small" onclick="copyText('${bank.account_number}')">کپی حساب</button>
          <button class="card small" onclick="copyText('${bank.sheba}')">کپی شبا</button>
          <button class="card small" onclick="copyText('${bank.owner_name}')">کپی نام</button>
        </div>
        <br>
        حالا از بخش «سفارش‌های من» رسید را ارسال کن.
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.uploadReceipt = async function(orderId) {
  const input = document.getElementById(`file-${orderId}`);
  if (!input.files || !input.files[0]) {
    alert("فایل را انتخاب کن");
    return;
  }

  const file = input.files[0];
  const reader = new FileReader();

  reader.onload = async function(event) {
    try {
      await postJSON(`/order/${orderId}/upload-receipt`, {
        user_id: currentUserId(),
        image_base64: event.target.result
      });
      alert("رسید ثبت شد");
      await loadUserOrders();
    } catch (e) {
      alert(e.message || "خطا");
    }
  };

  reader.readAsDataURL(file);
};

window.showOrderWallet = async function(orderId) {
  try {
    const data = await getJSON(`/order/${orderId}/wallet`);
    const wallet = data.wallet;

    setPanel(
      "ولت مقصد",
      `
      <div class="list-item">
        <strong>ارز:</strong> ${wallet.asset_code}<br>
        <strong>شبکه:</strong> ${wallet.network}<br>
        <strong>آدرس:</strong> ${wallet.address}<br><br>
        <button class="card small" onclick="copyText('${wallet.address}')">کپی آدرس</button>
        <br><br>
        بعد از انتقال، از بخش سفارش‌های من TXID را ثبت کن.
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.submitTx = async function(orderId) {
  const txid = document.getElementById(`tx-${orderId}`).value.trim();
  if (!txid) {
    alert("TXID را وارد کن");
    return;
  }

  try {
    await postJSON(`/order/${orderId}/submit-txid`, {
      user_id: currentUserId(),
      txid
    });
    alert("TXID ثبت شد");
    await loadUserOrders();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

adminPanelBtn.addEventListener("click", loadAdminHome);

async function loadAdminHome() {
  if (!isAdmin()) {
    setPanel("عدم دسترسی", "این بخش فقط برای ادمین است.");
    return;
  }

  try {
    const summary = await getJSON(`/admin/dashboard?admin_id=${currentUserId()}`);

    setPanel(
      "پنل ادمین",
      `
      <div class="stat-grid">
        <div class="stat-card">
          <div class="label">کل سفارش‌ها</div>
          <div class="value">${summary.order_count}</div>
        </div>
        <div class="stat-card">
          <div class="label">فعال</div>
          <div class="value">${summary.active_order_count}</div>
        </div>
        <div class="stat-card">
          <div class="label">خریدهای done</div>
          <div class="value">${formatIrr(summary.buy_total_irr)} ریال</div>
        </div>
        <div class="stat-card">
          <div class="label">فروش‌های done</div>
          <div class="value">${formatIrr(summary.sell_total_irr)} ریال</div>
        </div>
      </div>

      <div class="grid-actions three">
        <button class="card small" onclick="adminLoadOrders()">سفارش‌ها</button>
        <button class="card small" onclick="adminLoadInventory()">موجودی</button>
        <button class="card small" onclick="adminLoadBanks()">بانک‌ها</button>
        <button class="card small" onclick="adminLoadWallets()">ولت‌ها</button>
        <button class="card small" onclick="adminLoadNetworks()">شبکه‌ها</button>
        <button class="card small" onclick="adminLoadConfig()">تنظیمات</button>
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
}

window.adminLoadOrders = async function(status = "", query = "") {
  try {
    let path = `/admin/orders?admin_id=${currentUserId()}`;
    if (status) path += `&status=${encodeURIComponent(status)}`;
    if (query) path += `&order_id=${encodeURIComponent(query)}`;

    const orders = await getJSON(path);

    const filters = `
      <div class="list-item">
        <div class="form-group">
          <label>جست‌وجو با کد سفارش</label>
          <input id="orderSearch" type="text" placeholder="مثلاً ABC123" value="${query || ""}">
        </div>
        <div class="grid-actions three">
          <button class="card small" onclick="adminLoadOrders('', document.getElementById('orderSearch').value.trim())">همه</button>
          <button class="card small" onclick="adminLoadOrders('pending_admin', document.getElementById('orderSearch').value.trim())">pending</button>
          <button class="card small" onclick="adminLoadOrders('receipt_submitted', document.getElementById('orderSearch').value.trim())">receipt</button>
          <button class="card small" onclick="adminLoadOrders('txid_submitted', document.getElementById('orderSearch').value.trim())">txid</button>
          <button class="card small" onclick="adminLoadOrders('done', document.getElementById('orderSearch').value.trim())">done</button>
          <button class="card small" onclick="adminLoadOrders('rejected', document.getElementById('orderSearch').value.trim())">rejected</button>
        </div>
      </div>
    `;

    if (!orders.length) {
      setPanel("سفارش‌ها", filters + `<div class="list-item">سفارشی پیدا نشد</div>`);
      return;
    }

    const html = orders.map(o => `
      <div class="list-item">
        <strong>کد سفارش:</strong> ${o.order_id}<br>
        <strong>نوع:</strong> ${o.side === "buy" ? "خرید" : "فروش"}<br>
        <strong>ارز:</strong> ${o.asset_code}<br>
        <strong>شبکه:</strong> ${o.network}<br>
        <strong>مقدار:</strong> ${o.amount}<br>
        <strong>مبلغ:</strong> ${formatIrr(o.total_irr)} ریال<br>
        <strong>وضعیت:</strong> ${o.status}<br>
        <strong>TXID:</strong> ${o.txid || "-"}<br>
        <strong>رسید:</strong> ${o.receipt_url ? `<a href="${API_BASE}${o.receipt_url}" target="_blank">مشاهده</a>` : "ندارد"}<br><br>

        ${renderAdminActions(o)}

        <div class="form-group" style="margin-top:12px;">
          <label>ثبت/ویرایش TXID</label>
          <input id="txid-${o.order_id}" type="text" placeholder="TXID" value="${o.txid || ""}">
          <br><br>
          <button class="card small" onclick="adminSetTxid('${o.order_id}')">ذخیره TXID</button>
        </div>
      </div>
    `).join("");

    setPanel("مدیریت سفارش‌ها", filters + html);
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

function renderAdminActions(o) {
  if (o.status === "pending_admin") {
    return `
      <div class="grid-actions">
        <button class="card small green" onclick="adminApprove('${o.order_id}')">تأیید</button>
        <button class="card small red" onclick="adminSetOrderStatus('${o.order_id}','rejected')">رد</button>
      </div>
    `;
  }

  if (o.status === "receipt_submitted" || o.status === "txid_submitted") {
    return `
      <div class="grid-actions">
        <button class="card small green" onclick="adminSetOrderStatus('${o.order_id}','paid')">تأیید</button>
        <button class="card small red" onclick="adminSetOrderStatus('${o.order_id}','rejected')">رد</button>
      </div>
    `;
  }

  if (o.status === "paid" && o.side === "buy") {
    return `
      <div class="grid-actions">
        <button class="card small orange" onclick="adminSetOrderStatus('${o.order_id}','sent')">ارسال ارز</button>
        <button class="card small green" onclick="adminSetOrderStatus('${o.order_id}','done')">تکمیل</button>
      </div>
    `;
  }

  if (o.status === "paid" && o.side === "sell") {
    return `
      <div class="grid-actions">
        <button class="card small green" onclick="adminSetOrderStatus('${o.order_id}','done')">تکمیل</button>
      </div>
    `;
  }

  if (o.status === "sent") {
    return `
      <div class="grid-actions">
        <button class="card small green" onclick="adminSetOrderStatus('${o.order_id}','done')">تکمیل</button>
      </div>
    `;
  }

  return "";
}

window.adminApprove = async function(orderId) {
  try {
    await postJSON(`/admin/order/${orderId}/approve`, { admin_id: currentUserId() });
    alert("سفارش تأیید شد");
    await adminLoadOrders();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminSetOrderStatus = async function(orderId, status) {
  try {
    await postJSON(`/admin/order/${orderId}/status`, {
      admin_id: currentUserId(),
      status
    });
    alert("وضعیت تغییر کرد");
    await adminLoadOrders();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminSetTxid = async function(orderId) {
  try {
    const txid = document.getElementById(`txid-${orderId}`).value.trim();
    if (!txid) {
      alert("TXID را وارد کن");
      return;
    }
    await postJSON(`/admin/order/${orderId}/txid`, {
      admin_id: currentUserId(),
      txid
    });
    alert("TXID ذخیره شد");
    await adminLoadOrders();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminLoadInventory = async function() {
  try {
    const inventory = await getJSON(`/admin/inventory?admin_id=${currentUserId()}`);

    setPanel(
      "مدیریت موجودی",
      `
      ${["USDT", "TRX", "TON", "BNB"].map(asset => `
        <div class="list-item">
          <strong>${asset}</strong><br>
          موجودی فعلی: ${inventory[asset] ?? 0}
          <div class="form-group" style="margin-top:12px;">
            <label>مقدار</label>
            <input id="inv-${asset}" type="number" step="any" placeholder="مقدار">
          </div>
          <div class="grid-actions three">
            <button class="card small green" onclick="inventoryAdd('${asset}')">افزایش</button>
            <button class="card small red" onclick="inventoryRemove('${asset}')">کاهش</button>
            <button class="card small" onclick="inventorySet('${asset}')">تنظیم مستقیم</button>
          </div>
        </div>
      `).join("")}
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.inventoryAdd = async function(asset) {
  try {
    const amount = parseFloat(document.getElementById(`inv-${asset}`).value);
    if (!amount || amount <= 0) return alert("مقدار معتبر نیست");
    await postJSON("/admin/inventory/add", { admin_id: currentUserId(), asset_code: asset, amount });
    alert("افزایش یافت");
    await adminLoadInventory();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.inventoryRemove = async function(asset) {
  try {
    const amount = parseFloat(document.getElementById(`inv-${asset}`).value);
    if (!amount || amount <= 0) return alert("مقدار معتبر نیست");
    await postJSON("/admin/inventory/remove", { admin_id: currentUserId(), asset_code: asset, amount });
    alert("کاهش یافت");
    await adminLoadInventory();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.inventorySet = async function(asset) {
  try {
    const amount = parseFloat(document.getElementById(`inv-${asset}`).value);
    if (Number.isNaN(amount) || amount < 0) return alert("مقدار معتبر نیست");
    await postJSON("/admin/inventory/set", { admin_id: currentUserId(), asset_code: asset, amount });
    alert("تنظیم شد");
    await adminLoadInventory();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminLoadBanks = async function() {
  try {
    const banks = await getJSON(`/admin/banks?admin_id=${currentUserId()}`);

    setPanel(
      "مدیریت بانک‌ها",
      `
      <div class="list-item">
        <div class="form-group"><label>نام بانک</label><input id="bank_name"></div>
        <div class="form-group"><label>شماره حساب</label><input id="account_number"></div>
        <div class="form-group"><label>شبا</label><input id="sheba"></div>
        <div class="form-group"><label>شماره کارت</label><input id="card_number"></div>
        <div class="form-group"><label>نام صاحب حساب</label><input id="owner_name"></div>
        <button class="card small green" onclick="adminAddBank()">افزودن حساب بانکی</button>
      </div>

      ${banks.map(b => `
        <div class="list-item">
          <strong>${b.bank_name}</strong> - ${b.owner_name}<br>
          کارت: ${b.card_number}<br>
          حساب: ${b.account_number}<br>
          شبا: ${b.sheba}<br><br>
          <div class="grid-actions">
            <button class="card small" onclick="copyText('${b.card_number}')">کپی کارت</button>
            <button class="card small red" onclick="adminDeleteBank('${b.id}')">حذف</button>
          </div>
        </div>
      `).join("")}
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.adminAddBank = async function() {
  try {
    await postJSON("/admin/banks/add", {
      admin_id: currentUserId(),
      bank_name: document.getElementById("bank_name").value.trim(),
      account_number: document.getElementById("account_number").value.trim(),
      sheba: document.getElementById("sheba").value.trim(),
      card_number: document.getElementById("card_number").value.trim(),
      owner_name: document.getElementById("owner_name").value.trim()
    });
    alert("اضافه شد");
    await adminLoadBanks();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminDeleteBank = async function(bankId) {
  try {
    await postJSON("/admin/banks/delete", { admin_id: currentUserId(), bank_id: bankId });
    alert("حذف شد");
    await adminLoadBanks();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminLoadWallets = async function() {
  try {
    const wallets = await getJSON(`/admin/wallets?admin_id=${currentUserId()}`);

    setPanel(
      "مدیریت ولت‌ها",
      `
      <div class="list-item">
        <div class="form-group">
          <label>ارز</label>
          <select id="wallet_asset">
            <option value="USDT">USDT</option>
            <option value="TRX">TRX</option>
            <option value="TON">TON</option>
            <option value="BNB">BNB</option>
          </select>
        </div>
        <div class="form-group"><label>شبکه</label><input id="wallet_network" placeholder="مثلاً TRC20"></div>
        <div class="form-group"><label>آدرس ولت</label><input id="wallet_address"></div>
        <button class="card small green" onclick="adminAddWallet()">افزودن ولت</button>
      </div>

      ${wallets.map(w => `
        <div class="list-item">
          <strong>${w.asset_code}</strong> - ${w.network}<br>
          آدرس: ${w.address}<br><br>
          <div class="grid-actions">
            <button class="card small" onclick="copyText('${w.address}')">کپی</button>
            <button class="card small red" onclick="adminDeleteWallet('${w.id}')">حذف</button>
          </div>
        </div>
      `).join("")}
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.adminAddWallet = async function() {
  try {
    await postJSON("/admin/wallets/add", {
      admin_id: currentUserId(),
      asset_code: document.getElementById("wallet_asset").value,
      network: document.getElementById("wallet_network").value.trim(),
      address: document.getElementById("wallet_address").value.trim()
    });
    alert("اضافه شد");
    await adminLoadWallets();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminDeleteWallet = async function(walletId) {
  try {
    await postJSON("/admin/wallets/delete", { admin_id: currentUserId(), wallet_id: walletId });
    alert("حذف شد");
    await adminLoadWallets();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminLoadNetworks = async function() {
  try {
    const data = await getJSON(`/admin/networks?admin_id=${currentUserId()}`);

    setPanel(
      "مدیریت شبکه‌ها",
      `
      <div class="list-item">
        <div class="form-group">
          <label>ارز</label>
          <select id="network_asset">
            <option value="USDT">USDT</option>
            <option value="TRX">TRX</option>
            <option value="TON">TON</option>
            <option value="BNB">BNB</option>
          </select>
        </div>
        <div class="form-group"><label>نام شبکه</label><input id="network_name"></div>
        <div class="form-group">
          <label>ارز کارمزد</label>
          <select id="fee_asset">
            <option value="USDT">USDT</option>
            <option value="TRX">TRX</option>
            <option value="TON">TON</option>
            <option value="BNB">BNB</option>
          </select>
        </div>
        <div class="form-group"><label>مقدار کارمزد</label><input id="fee_amount" type="number" step="any"></div>
        <button class="card small green" onclick="adminAddNetwork()">افزودن شبکه</button>
      </div>

      ${Object.keys(data).map(asset => `
        <div class="list-item">
          <strong>${asset}</strong><br><br>
          ${Object.keys(data[asset].networks).map(net => `
            <div style="margin-bottom:8px;">
              ${net} | fee: ${data[asset].networks[net].fee_amount} ${data[asset].networks[net].fee_asset}
              <br>
              <button class="card small red" style="margin-top:8px;" onclick="adminDeleteNetwork('${asset}','${net}')">حذف ${net}</button>
            </div>
          `).join("")}
        </div>
      `).join("")}
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.adminAddNetwork = async function() {
  try {
    await postJSON("/admin/networks/add", {
      admin_id: currentUserId(),
      asset_code: document.getElementById("network_asset").value,
      network: document.getElementById("network_name").value.trim(),
      fee_asset: document.getElementById("fee_asset").value,
      fee_amount: parseFloat(document.getElementById("fee_amount").value)
    });
    alert("اضافه شد");
    await adminLoadNetworks();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminDeleteNetwork = async function(asset, network) {
  try {
    await postJSON("/admin/networks/delete", {
      admin_id: currentUserId(),
      asset_code: asset,
      network
    });
    alert("حذف شد");
    await adminLoadNetworks();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

window.adminLoadConfig = async function() {
  try {
    const cfg = await getJSON(`/admin/config?admin_id=${currentUserId()}`);

    setPanel(
      "تنظیمات قیمت",
      `
      <div class="list-item">
        <div class="form-group">
          <label>حالت نرخ تتر</label>
          <select id="cfg_mode">
            <option value="manual" ${cfg.usdt_price_mode === "manual" ? "selected" : ""}>دستی</option>
            <option value="exchange" ${cfg.usdt_price_mode === "exchange" ? "selected" : ""}>صرافی‌ها</option>
          </select>
        </div>

        <div class="form-group">
          <label>منبع نرخ صرافی</label>
          <select id="cfg_source">
            <option value="auto" ${cfg.usdt_exchange_source === "auto" ? "selected" : ""}>خودکار</option>
            <option value="nobitex" ${cfg.usdt_exchange_source === "nobitex" ? "selected" : ""}>Nobitex</option>
            <option value="wallex" ${cfg.usdt_exchange_source === "wallex" ? "selected" : ""}>Wallex</option>
          </select>
        </div>

        <div class="form-group">
          <label>نرخ دستی تتر (ریال)</label>
          <input id="cfg_usdt" type="number" step="any" value="${cfg.usdt_manual_price_irr}">
        </div>

        <div class="form-group">
          <label>آخرین نرخ کش‌شده</label>
          <input type="text" disabled value="${cfg.usdt_cached_price_irr || "-"} | ${cfg.usdt_cached_at || "-"}">
        </div>

        <div class="form-group">
          <label>سود خرید (%)</label>
          <input id="cfg_buy" type="number" step="any" value="${cfg.my_profit_percent_buy}">
        </div>

        <div class="form-group">
          <label>سود فروش (%)</label>
          <input id="cfg_sell" type="number" step="any" value="${cfg.my_profit_percent_sell}">
        </div>

        <div class="form-group">
          <label>مارک‌آپ بایننس (%)</label>
          <input id="cfg_markup" type="number" step="any" value="${cfg.binance_markup_percent}">
        </div>

        <button class="card small green" onclick="adminSaveConfig()">ذخیره تنظیمات</button>
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا");
  }
};

window.adminSaveConfig = async function() {
  try {
    await postJSON("/admin/config/update", {
      admin_id: currentUserId(),
      usdt_price_mode: document.getElementById("cfg_mode").value,
      usdt_exchange_source: document.getElementById("cfg_source").value,
      usdt_manual_price_irr: parseFloat(document.getElementById("cfg_usdt").value),
      my_profit_percent_buy: parseFloat(document.getElementById("cfg_buy").value),
      my_profit_percent_sell: parseFloat(document.getElementById("cfg_sell").value),
      binance_markup_percent: parseFloat(document.getElementById("cfg_markup").value)
    });
    alert("ذخیره شد");
    await adminLoadConfig();
  } catch (e) {
    alert(e.message || "خطا");
  }
};

initUi();
loadHome();