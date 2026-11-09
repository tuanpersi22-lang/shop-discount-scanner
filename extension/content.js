(() => {
  if (window.__shopDiscountScannerInstalled) return;
  window.__shopDiscountScannerInstalled = true;

  const MAX_PRODUCTS = 300;
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

  function moneyFromText(value) {
    const text = clean(value).replace(/\u00a0/g, " ");
    const match = text.match(/(?:₫|đ|VND)\s*([\d.,]+)|([\d.,]+)\s*(?:₫|đ|VND)/i);
    if (!match) return null;
    const digits = (match[1] || match[2] || "").replace(/[.,]/g, "");
    const amount = Number(digits);
    return Number.isFinite(amount) && amount > 0 ? amount : null;
  }

  function productUrl(anchor) {
    if (!anchor || !anchor.href) return "";
    try {
      const url = new URL(anchor.href, location.href);
      if (url.hostname !== "shopee.vn" && !url.hostname.endsWith(".shopee.vn")) return "";
      if (/\/product\/\d+\/\d+/.test(url.pathname) || /-i\.\d+\.\d+/.test(url.pathname) || /itemid=/i.test(url.search)) {
        return url.href.split("#")[0];
      }
    } catch (_) {}
    return "";
  }

  function findCard(anchor) {
    const marked = anchor.closest('[data-sqe="item"]');
    if (marked) return marked;
    let node = anchor;
    for (let depth = 0; node && depth < 9; depth += 1, node = node.parentElement) {
      const text = clean(node.innerText || node.textContent);
      if (text.length >= 25 && text.length <= 700 && /₫|đ|VND/i.test(text)) return node;
    }
    return anchor.parentElement || anchor;
  }

  function priceElements(card) {
    return Array.from(card.querySelectorAll(
      'del, s, strike, [class*="price"], [class*="Price"], [data-sqe*="price"]'
    )).filter((element) => {
      const text = clean(element.innerText || element.textContent);
      return text.length > 0 && text.length < 90 && moneyFromText(text) !== null;
    });
  }

  function getPrices(card) {
    const elements = priceElements(card);
    let listPrice = null;
    let salePrice = null;

    for (const element of elements) {
      const text = clean(element.innerText || element.textContent);
      const className = typeof element.className === "string" ? element.className : "";
      let struck = ["del", "s", "strike"].includes(element.tagName.toLowerCase())
        || /old|original|origin|strike|compare|regular/i.test(className);
      try {
        if (getComputedStyle(element).textDecorationLine.includes("line-through")) struck = true;
      } catch (_) {}
      const amount = moneyFromText(text);
      if (struck && listPrice === null) listPrice = amount;
      if (!struck && salePrice === null) salePrice = amount;
    }

    const text = clean(card.innerText || card.textContent);
    const amounts = Array.from(text.matchAll(/(?:₫|đ|VND)\s*([\d.,]+)|([\d.,]+)\s*(?:₫|đ|VND)/gi))
      .map((match) => Number((match[1] || match[2] || "").replace(/[.,]/g, "")))
      .filter((amount) => Number.isFinite(amount) && amount > 0);

    if (salePrice === null && amounts.length) salePrice = amounts[0];
    if (listPrice === null && elements.some((element) => {
      const cls = typeof element.className === "string" ? element.className : "";
      return ["del", "s", "strike"].includes(element.tagName.toLowerCase())
        || /old|original|origin|strike|compare|regular/i.test(cls);
    })) {
      listPrice = amounts.find((amount) => amount !== salePrice) || null;
    }

    const discountMatch = text.match(/-\s*(\d+(?:[.,]\d+)?)\s*%|(\d+(?:[.,]\d+)?)\s*%\s*(?:OFF|GIẢM)/i);
    let explicitDiscount = discountMatch
      ? Number((discountMatch[1] || discountMatch[2]).replace(",", "."))
      : null;
    if (explicitDiscount !== null && (!Number.isFinite(explicitDiscount) || explicitDiscount <= 0 || explicitDiscount >= 100)) {
      explicitDiscount = null;
    }
    if (listPrice === null && salePrice !== null && explicitDiscount !== null) {
      listPrice = Math.round(salePrice / (1 - explicitDiscount / 100));
    }
    return { salePrice, listPrice };
  }

  function getName(anchor, card) {
    const selectors = [
      '[data-sqe="name"]', '[class*="name"]', '[class*="Name"]',
      "h1", "h2", "h3"
    ];
    for (const selector of selectors) {
      const element = card.querySelector(selector);
      const value = clean(element && (element.innerText || element.textContent));
      if (value.length >= 3 && !/₫|đ|VND/i.test(value)) return value.slice(0, 300);
    }
    const image = anchor.querySelector("img") || card.querySelector("img");
    const alt = clean(image && image.alt);
    if (alt.length >= 3) return alt.slice(0, 300);

    const lines = (card.innerText || card.textContent || "")
      .split(/\n+/).map(clean)
      .filter((line) => line.length >= 4 && !/₫|đ|VND|%|đã bán|sold|freeship|miễn phí/i.test(line));
    return (lines[0] || clean(anchor.getAttribute("aria-label")) || "Chưa đọc được tên sản phẩm").slice(0, 300);
  }

  function makeRow(anchor, card, shop) {
    const url = productUrl(anchor);
    const { salePrice, listPrice } = getPrices(card);
    if (!url || salePrice === null) return null;
    const name = getName(anchor, card);
    const ratio = listPrice && listPrice > 0 ? Number((salePrice / listPrice * 100).toFixed(2)) : null;
    const discount = listPrice && listPrice > 0 ? Number(((1 - salePrice / listPrice) * 100).toFixed(2)) : null;
    return {
      "Shop": shop,
      "Sản phẩm": name,
      "Biến thể": "",
      "SKU": "",
      "Giá niêm yết": listPrice,
      "Giá bán": salePrice,
      "Tỷ lệ giá bán (%)": ratio,
      "Chiết khấu (%)": discount,
      "Tiền tệ": "VND",
      "Trạng thái": listPrice === null ? "Thiếu giá niêm yết" : (discount > 0 ? "Có chiết khấu" : "Không giảm giá"),
      "URL sản phẩm": url,
      "Nguồn giá": "Chrome extension (Shopee DOM)",
      "Thời điểm quét": new Date().toLocaleString("sv-SE")
    };
  }

  function collectRows() {
    const firstSegment = location.pathname.split("/").filter(Boolean)[0] || "Shopee";
    const shop = firstSegment;
    const anchors = Array.from(document.querySelectorAll("a[href]"));
    const seen = new Set();
    const rows = [];

    for (const anchor of anchors) {
      const url = productUrl(anchor);
      if (!url || seen.has(url)) continue;
      seen.add(url);
      const card = findCard(anchor);
      const row = makeRow(anchor, card, shop);
      if (row) rows.push(row);
      if (rows.length >= MAX_PRODUCTS) break;
    }

    if (rows.length === 0) {
      const heading = document.querySelector("h1");
      const title = clean(heading && (heading.innerText || heading.textContent));
      if (title) {
        const detailRoot = document.querySelector("main") || document.body;
        const prices = getPrices(detailRoot);
        if (prices.salePrice !== null) {
          const list = prices.listPrice;
          const ratio = list ? Number((prices.salePrice / list * 100).toFixed(2)) : null;
          const discount = list ? Number(((1 - prices.salePrice / list) * 100).toFixed(2)) : null;
          rows.push({
            "Shop": shop, "Sản phẩm": title, "Biến thể": "", "SKU": "",
            "Giá niêm yết": list, "Giá bán": prices.salePrice,
            "Tỷ lệ giá bán (%)": ratio, "Chiết khấu (%)": discount,
            "Tiền tệ": "VND",
            "Trạng thái": list === null ? "Thiếu giá niêm yết" : (discount > 0 ? "Có chiết khấu" : "Không giảm giá"),
            "URL sản phẩm": location.href.split("#")[0],
            "Nguồn giá": "Chrome extension (Shopee DOM)",
            "Thời điểm quét": new Date().toLocaleString("sv-SE")
          });
        }
      }
    }
    return rows;
  }

  async function scanPage() {
    const originalY = window.scrollY;
    const rowsByUrl = new Map();
    let previousHeight = 0;
    let stablePasses = 0;

    for (let pass = 0; pass < 18; pass += 1) {
      for (const row of collectRows()) rowsByUrl.set(row["URL sản phẩm"], row);
      const height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
      if (height === previousHeight) stablePasses += 1;
      else stablePasses = 0;
      if (stablePasses >= 2 || rowsByUrl.size >= MAX_PRODUCTS) break;
      previousHeight = height;
      window.scrollTo(0, height);
      await sleep(350);
    }

    for (const row of collectRows()) rowsByUrl.set(row["URL sản phẩm"], row);
    window.scrollTo(0, originalY);
    return {
      rows: Array.from(rowsByUrl.values()).slice(0, MAX_PRODUCTS),
      pageUrl: location.href,
      pageTitle: document.title
    };
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message && message.type === "SHOP_DISCOUNT_SCAN") {
      scanPage().then(sendResponse).catch((error) => {
        sendResponse({ rows: [], error: String(error && error.message || error) });
      });
      return true;
    }
    return false;
  });
})();
