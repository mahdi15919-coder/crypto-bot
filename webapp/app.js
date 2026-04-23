const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const API_BASE = "https://crypto-bot-api-atmh.onrender.com";
const ADMIN_ID = 5869677184;

const welcomeText = document.getElementById("welcomeText");
const panelTitle = document.getElementById("panelTitle");
const panelBody = document.getElementById("panelBody");

const showPricesBtn = document.getElementById("showPricesBtn");
const buySellBtn = document.getElementById("buySellBtn");
const showOrdersBtn = document.getElementById("showOrdersBtn");
const showBanksBtn = document.getElementById("showBanksBtn");
const showWalletsBtn = document.getElementById("showWalletsBtn");
const adminPanelBtn = document.getElementById("adminPanelBtn");

let orderData = {};

function currentUserId() {
  return tg?.initDataUnsafe?.user?.id;
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

function copyText(text) {
  navigator.clipboard.writeText(text)
    .then(() => alert("کپی شد"))
    .catch(() => alert("کپی نشد"));
}

async function loadSummary() {
  try {
    const data = await getJSON("/summary");
    const userName =
      tg?.initDataUnsafe?.user?.first_name ||
      tg?.initDataUnsafe?.user?.username ||
      "دوست عزیز";

    welcomeText.textContent = `سلام ${userName}، پنل آماده‌ست.`;

    setPanel(
      "داشبورد",
      `
      قیمت فروش تتر: <strong>${formatIrr(data.usdt_prices.sell_to_user)}</strong> ریال
      <br>
      قیمت خرید تتر: <strong>${formatIrr(data.usdt_prices.buy_from_user)}</strong> ریال
      <br><br>
      تعداد حساب‌های بانکی: <strong>${data.bank_count}</strong>
      <br>
      تعداد ولت‌ها: <strong>${data.wallet_count}</strong>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا در بارگذاری اطلاعات");
  }
}

showPricesBtn.addEventListener("click", async () => {
  try {
    const data = await getJSON("/summary");
    setPanel(
      "قیمت تتر",
      `
      🟢 فروش به شما: <strong>${formatIrr(data.usdt_prices.sell_to_user)}</strong> ریال
      <br>
      🔴 خرید از شما: <strong>${formatIrr(data.usdt_prices.buy_from_user)}</strong> ریال
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا در دریافت قیمت");
  }
});

buySellBtn.addEventListener("click", () => {
  orderData = {};
  setPanel(
    "نوع معامله",
    `
    <div class="list-item">
      <div class="grid-actions">
        <button class="card small success" onclick="selectSide('buy')">🟢 خرید</button>
        <button class="card small danger" onclick="selectSide('sell')">🔴 فروش</button>
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
      .map(
        (n) => `<button class="card small" onclick="selectNetwork('${n}')">${n}</button>`
      )
      .join("");

    setPanel(
      "انتخاب شبکه",
      `<div class="list-item"><div class="grid-actions">${buttons}</div></div>`
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا در دریافت شبکه‌ها");
  }
};

window.selectNetwork = function(network) {
  orderData.network = network;

  setPanel(
    "مقدار",
    `
    <div class="list-item">
      <label>مقدار:</label>
      <br><br>
      <input id="amountInput" type="number" step="any" placeholder="مثلاً 10">
      <br><br>
      <button class="card small" onclick="getQuote()">ادامه</button>
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

    orderData.quote = quote;

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
        <label>آدرس مقصد / مبدا:</label><br><br>
        <input id="walletAddressInput" type="text" placeholder="آدرس را وارد کن">
        <br><br>
        <button class="card small warning" onclick="submitOrder()">ثبت سفارش</button>
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا در محاسبه قیمت");
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
    alert("شناسه کاربر تلگرام پیدا نشد");
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

    const order = data.order;

    if (order.side === "buy") {
      await showBankSelection(order.order_id);
    } else {
      await showOrderWallet(order.order_id);
    }
  } catch (e) {
    setPanel("خطا", e.message || "خطا در ثبت سفارش");
  }
};

async function showBankSelection(orderId) {
  try {
    const banks = await getJSON("/banks");

    if (!banks.length) {
      setPanel(
        "ثبت شد",
        `
        <div class="list-item">
          ✅ سفارش ثبت شد<br><br>
          <strong>کد سفارش:</strong> ${orderId}<br>
          <strong>وضعیت:</strong> pending<br><br>
          ⚠️ هنوز هیچ حساب بانکی ثبت نشده.
        </div>
        `
      );
      return;
    }

    const html = banks.map(
      (b) => `
      <div class="list-item">
        <strong>${b.bank_name}</strong> - ${b.owner_name}<br><br>
        <button class="card small" onclick="selectBankForOrder('${orderId}', '${b.id}')">انتخاب این حساب</button>
      </div>
      `
    ).join("");

    setPanel(
      "انتخاب حساب بانکی",
      `
      <div class="list-item">
        برای پرداخت یکی از حساب‌ها را انتخاب کن.<br><br>
        ترجیحاً از همان بانک و به‌صورت حساب‌به‌حساب واریز کن.
      </div>
      ${html}
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا در دریافت حساب‌ها");
  }
}

window.selectBankForOrder = async function(orderId, bankId) {
  try {
    const data = await postJSON(`/order/${orderId}/select-bank`, {
      bank_id: bankId
    });

    const bank = data.bank;

    setPanel(
      "اطلاعات پرداخت",
      `
      <div class="list-item">
        <strong>کد سفارش:</strong> ${orderId}<br>
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
        لطفاً در صورت امکان از همین بانک و به‌صورت حساب‌به‌حساب واریز کن.
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا در انتخاب بانک");
  }
};

async function showOrderWallet(orderId) {
  try {
    const data = await getJSON(`/order/${orderId}/wallet`);
    const wallet = data.wallet;

    setPanel(
      "آدرس ولت",
      `
      <div class="list-item">
        <strong>کد سفارش:</strong> ${orderId}<br>
        <strong>ارز:</strong> ${wallet.asset_code}<br>
        <strong>شبکه:</strong> ${wallet.network}<br>
        <strong>آدرس:</strong> ${wallet.address}<br><br>
        <button class="card small" onclick="copyText('${wallet.address}')">کپی آدرس ولت</button>
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "ولت مناسب پیدا نشد");
  }
}

showOrdersBtn.addEventListener("click", async () => {
  try {
    const userId = currentUserId();
    if (!userId) {
      setPanel("سفارش‌ها", "شناسه کاربر تلگرام در دسترس نیست");
      return;
    }

    const orders = await getJSON(`/orders?user_id=${userId}`);

    if (!orders.length) {
      setPanel("سفارش‌های من", "هنوز سفارشی ثبت نشده");
      return;
    }

    const html = orders
      .slice()
      .reverse()
      .map(
        (o) => `
        <div class="list-item">
          <strong>کد سفارش:</strong> ${o.order_id}<br>
          <strong>نوع:</strong> ${o.side === "buy" ? "خرید" : "فروش"}<br>
          <strong>ارز:</strong> ${o.asset_code}<br>
          <strong>شبکه:</strong> ${o.network}<br>
          <strong>مقدار:</strong> ${o.amount}<br>
          <strong>مبلغ:</strong> ${formatIrr(o.total_irr)} ریال<br>
          <strong>وضعیت:</strong> ${o.status}
        </div>
      `
      )
      .join("");

    setPanel("سفارش‌های من", html);
  } catch (e) {
    setPanel("خطا", e.message || "خطا در دریافت سفارش‌ها");
  }
});

showBanksBtn.addEventListener("click", async () => {
  try {
    const banks = await getJSON("/banks");

    if (!banks.length) {
      setPanel("حساب‌های بانکی", "هیچ حساب بانکی ثبت نشده");
      return;
    }

    const html = banks
      .map(
        (b) => `
        <div class="list-item">
          <strong>بانک:</strong> ${b.bank_name}<br>
          <strong>صاحب حساب:</strong> ${b.owner_name}<br>
          <strong>کارت:</strong> ${b.card_number}<br>
          <strong>شبا:</strong> ${b.sheba}<br>
          <strong>حساب:</strong> ${b.account_number}<br><br>
          <div class="grid-actions">
            <button class="card small" onclick="copyText('${b.card_number}')">کپی کارت</button>
            <button class="card small" onclick="copyText('${b.sheba}')">کپی شبا</button>
          </div>
        </div>
      `
      )
      .join("");

    setPanel("حساب‌های بانکی", html);
  } catch (e) {
    setPanel("خطا", e.message || "خطا در دریافت حساب‌های بانکی");
  }
});

showWalletsBtn.addEventListener("click", async () => {
  try {
    const wallets = await getJSON("/wallets");

    if (!wallets.length) {
      setPanel("ولت‌ها", "هیچ ولتی ثبت نشده");
      return;
    }

    const html = wallets
      .map(
        (w) => `
        <div class="list-item">
          <strong>ارز:</strong> ${w.asset_code}<br>
          <strong>شبکه:</strong> ${w.network}<br>
          <strong>آدرس:</strong> ${w.address}<br><br>
          <button class="card small" onclick="copyText('${w.address}')">کپی آدرس</button>
        </div>
      `
      )
      .join("");

    setPanel("ولت‌ها", html);
  } catch (e) {
    setPanel("خطا", e.message || "خطا در دریافت ولت‌ها");
  }
});

adminPanelBtn.addEventListener("click", async () => {
  if (!isAdmin()) {
    setPanel("عدم دسترسی", "این بخش فقط برای ادمین است.");
    return;
  }

  try {
    const adminId = currentUserId();
    const summary = await getJSON(`/admin/summary?admin_id=${adminId}`);

    setPanel(
      "پنل ادمین",
      `
      <div class="list-item">
        <strong>تعداد کل سفارش‌ها:</strong> ${summary.order_count}<br>
        <strong>سفارش‌های فعال:</strong> ${summary.active_order_count}<br>
        <strong>تعداد حساب‌های بانکی:</strong> ${summary.bank_count}<br>
        <strong>تعداد ولت‌ها:</strong> ${summary.wallet_count}
      </div>

      <div class="list-item">
        <strong>موجودی:</strong><br>
        USDT: ${summary.inventory.USDT ?? 0}<br>
        TRX: ${summary.inventory.TRX ?? 0}<br>
        TON: ${summary.inventory.TON ?? 0}<br>
        BNB: ${summary.inventory.BNB ?? 0}
      </div>

      <div class="grid-actions">
        <button class="card small" onclick="loadAdminOrders()">مدیریت سفارش‌ها</button>
      </div>
      `
    );
  } catch (e) {
    setPanel("خطا", e.message || "خطا در پنل ادمین");
  }
});

window.loadAdminOrders = async function() {
  try {
    const adminId = currentUserId();
    const orders = await getJSON(`/admin/orders?admin_id=${adminId}`);

    if (!orders.length) {
      setPanel("سفارش‌ها", "سفارشی وجود ندارد");
      return;
    }

    const html = orders.map(
      (o) => `
      <div class="list-item">
        <strong>کد سفارش:</strong> ${o.order_id}<br>
        <strong>نوع:</strong> ${o.side === "buy" ? "خرید" : "فروش"}<br>
        <strong>ارز:</strong> ${o.asset_code}<br>
        <strong>شبکه:</strong> ${o.network}<br>
        <strong>مقدار:</strong> ${o.amount}<br>
        <strong>مبلغ:</strong> ${formatIrr(o.total_irr)} ریال<br>
        <strong>وضعیت:</strong> ${o.status}<br><br>

        <div class="grid-actions">
          <button class="card small success" onclick="setOrderStatus('${o.order_id}', 'approved')">approved</button>
          <button class="card small warning" onclick="setOrderStatus('${o.order_id}', 'paid')">paid</button>
          <button class="card small" onclick="setOrderStatus('${o.order_id}', 'sent')">sent</button>
          <button class="card small" onclick="setOrderStatus('${o.order_id}', 'done')">done</button>
          <button class="card small danger" onclick="setOrderStatus('${o.order_id}', 'rejected')">rejected</button>
        </div>
      </div>
      `
    ).join("");

    setPanel("مدیریت سفارش‌ها", html);
  } catch (e) {
    setPanel("خطا", e.message || "خطا در دریافت سفارش‌ها");
  }
};

window.setOrderStatus = async function(orderId, status) {
  try {
    const adminId = currentUserId();
    await postJSON(`/admin/order/${orderId}/status`, {
      admin_id: adminId,
      status: status
    });

    alert("وضعیت سفارش تغییر کرد");
    await loadAdminOrders();
  } catch (e) {
    alert(e.message || "خطا در تغییر وضعیت");
  }
};

loadSummary();