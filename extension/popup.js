const SCANNER_URL = "https://shop-discount-scanner.onrender.com/";
const CSV_COLUMNS = [
  "Shop", "Sản phẩm", "Biến thể", "SKU", "Giá niêm yết", "Giá bán",
  "Tỷ lệ giá bán (%)", "Chiết khấu (%)", "Tiền tệ", "Trạng thái",
  "URL sản phẩm", "Nguồn giá", "Thời điểm quét"
];

let rows = [];

const statusEl = document.getElementById("status");
const countEl = document.getElementById("count");
const scanButton = document.getElementById("scan");
const downloadButton = document.getElementById("download");
const openButton = document.getElementById("open");

function setStatus(message, kind = "") {
  statusEl.textContent = message;
  statusEl.className = "status" + (kind ? " " + kind : "");
}

function csvCell(value) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
}

function makeCsv(items) {
  const lines = [CSV_COLUMNS.map(csvCell).join(",")];
  for (const item of items) lines.push(CSV_COLUMNS.map((column) => csvCell(item[column])).join(","));
  return "\uFEFF" + lines.join("\r\n");
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

async function restoreLastScan() {
  const saved = await chrome.storage.local.get(["lastScan"]);
  if (saved.lastScan && Array.isArray(saved.lastScan.rows)) {
    rows = saved.lastScan.rows;
    countEl.textContent = rows.length + " sản phẩm trong lần quét gần nhất.";
    downloadButton.disabled = rows.length === 0;
  }
  const tab = await getActiveTab();
  if (!tab || !tab.url || !/^https:\/\/([^.]+\.)?shopee\.vn\//i.test(tab.url)) {
    setStatus("Hãy mở một trang Shopee.vn rồi bấm quét.");
  } else {
    setStatus("Đã sẵn sàng quét trang Shopee hiện tại.", "success");
  }
}

scanButton.addEventListener("click", async () => {
  scanButton.disabled = true;
  downloadButton.disabled = true;
  setStatus("Đang đọc sản phẩm và cuộn trang để tải thêm dữ liệu…");
  try {
    const tab = await getActiveTab();
    if (!tab || !tab.id || !tab.url || !/^https:\/\/([^.]+\.)?shopee\.vn\//i.test(tab.url)) {
      throw new Error("Bạn cần mở trang Shopee.vn trước khi quét.");
    }
    const result = await chrome.tabs.sendMessage(tab.id, { type: "SHOP_DISCOUNT_SCAN" });
    if (result && result.error) throw new Error(result.error);
    rows = result && Array.isArray(result.rows) ? result.rows : [];
    await chrome.storage.local.set({ lastScan: { rows, pageUrl: tab.url, scannedAt: new Date().toISOString() } });
    countEl.textContent = rows.length + " sản phẩm được đọc từ trang hiện tại.";
    if (rows.length) {
      setStatus("Quét xong. Hãy tải CSV để lập báo cáo.", "success");
      downloadButton.disabled = false;
    } else {
      setStatus("Chưa đọc được sản phẩm có giá. Hãy mở trang danh mục, chờ sản phẩm hiện ra rồi thử lại.", "error");
    }
  } catch (error) {
    setStatus(error && error.message ? error.message : "Không thể quét trang. Hãy tải lại trang Shopee rồi thử lại.", "error");
  } finally {
    scanButton.disabled = false;
  }
});

downloadButton.addEventListener("click", async () => {
  if (!rows.length) return;
  const blob = new Blob([makeCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const filename = "shopee_products_" + new Date().toISOString().replace(/[:.]/g, "-") + ".csv";
  try {
    await chrome.downloads.download({ url, filename, saveAs: true });
    setStatus("Đã gửi file CSV tới mục tải xuống.", "success");
  } catch (error) {
    setStatus("Không tải được CSV: " + (error.message || error), "error");
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
});

openButton.addEventListener("click", () => {
  chrome.tabs.create({ url: SCANNER_URL });
});

restoreLastScan().catch(() => setStatus("Hãy mở trang Shopee.vn rồi bấm quét."));
