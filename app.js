/**
 * BLOCKSMITH // Mini-Blockchain Explorer & PoW Studio
 * Frontend Application Engine (supports live Python REST API & offline WebCrypto fallback)
 */

// Global State
let isBackendConnected = false;
let blockchainState = null;
let isMiningInProgress = false;
let currentTamperedBlockIndex = null;

// DOM Elements
const connectionStatus = document.getElementById("connectionStatus");
const connectionText = document.getElementById("connectionText");
const chainHealthBadge = document.getElementById("chainHealthBadge");
const chainHealthText = document.getElementById("chainHealthText");
const validationAlert = document.getElementById("validationAlert");
const alertTitle = document.getElementById("alertTitle");
const alertDescription = document.getElementById("alertDescription");

const statHeight = document.getElementById("statHeight");
const statHeightSub = document.getElementById("statHeightSub");
const statDifficulty = document.getElementById("statDifficulty");
const statTargetPrefix = document.getElementById("statTargetPrefix");
const statSupply = document.getElementById("statSupply");
const statMempool = document.getElementById("statMempool");
const blockCountBadge = document.getElementById("blockCountBadge");

const blocksContainer = document.getElementById("blocksContainer");
const balancesGrid = document.getElementById("balancesGrid");
const mempoolList = document.getElementById("mempoolList");
const mempoolBadge = document.getElementById("mempoolBadge");

const difficultySlider = document.getElementById("difficultySlider");
const difficultyVal = document.getElementById("difficultyVal");
const minerSelect = document.getElementById("minerSelect");
const btnMineBlock = document.getElementById("btnMineBlock");
const miningStatusBadge = document.getElementById("miningStatusBadge");

const liveNonce = document.getElementById("liveNonce");
const liveHash = document.getElementById("liveHash");
const liveAttempts = document.getElementById("liveAttempts");
const liveTimer = document.getElementById("liveTimer");
const liveHashRate = document.getElementById("liveHashRate");

const btnAuditChain = document.getElementById("btnAuditChain");
const btnResetChain = document.getElementById("btnResetChain");
const btnDismissAlert = document.getElementById("btnDismissAlert");

const btnTamperPreset = document.getElementById("btnTamperPreset");
const btnRemineBlock1 = document.getElementById("btnRemineBlock1");
const btnRepairChain = document.getElementById("btnRepairChain");
const tamperNotes = document.getElementById("tamperNotes");

const txForm = document.getElementById("txForm");
const txSender = document.getElementById("txSender");
const txReceiver = document.getElementById("txReceiver");
const txAmount = document.getElementById("txAmount");
const btnClearMempool = document.getElementById("btnClearMempool");

const merkleModal = document.getElementById("merkleModal");
const btnCloseMerkleModal = document.getElementById("btnCloseMerkleModal");
const merkleTreeCanvas = document.getElementById("merkleTreeCanvas");

const tamperModal = document.getElementById("tamperModal");
const btnCloseTamperModal = document.getElementById("btnCloseTamperModal");
const btnCancelTamper = document.getElementById("btnCancelTamper");
const btnConfirmTamper = document.getElementById("btnConfirmTamper");
const tamperPayloadJson = document.getElementById("tamperPayloadJson");
const tamperModalTitle = document.getElementById("tamperModalTitle");

const toastContainer = document.getElementById("toastContainer");

/* ==========================================================================
   Web Cryptography Standalone Fallback Engine
   ========================================================================== */

async function sha256(message) {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

function deterministicJson(obj) {
  return JSON.stringify(obj, Object.keys(obj).sort());
}

async function computeMerkleRootJs(data) {
  if (!Array.isArray(data)) {
    return sha256(deterministicJson(data));
  }
  if (data.length === 0) {
    return sha256("");
  }
  let currentLevel = [];
  for (const item of data) {
    currentLevel.push(await sha256(deterministicJson(item)));
  }
  while (currentLevel.length > 1) {
    if (currentLevel.length % 2 !== 0) {
      currentLevel.push(currentLevel[currentLevel.length - 1]);
    }
    const nextLevel = [];
    for (let i = 0; i < currentLevel.length; i += 2) {
      const combined = currentLevel[i] + currentLevel[i + 1];
      nextLevel.push(await sha256(combined));
    }
    currentLevel = nextLevel;
  }
  return currentLevel[0];
}

class InBrowserBlockchain {
  constructor(difficulty = 3, miningReward = 50.0) {
    this.difficulty = difficulty;
    this.miningReward = miningReward;
    this.chain = [];
    this.pendingTransactions = [];
  }

  async init() {
    this.chain = [];
    this.pendingTransactions = [];
    // Genesis
    const genesisData = "Genesis Block";
    const merkleRoot = await computeMerkleRootJs(genesisData);
    const genesisBlock = {
      index: 0,
      timestamp: Date.now() / 1000,
      data: genesisData,
      previous_hash: "0",
      nonce: 0,
      merkle_root: merkleRoot,
      hash: "",
    };
    await this.mineBlock(genesisBlock);
    this.chain.push(genesisBlock);

    // Block 1
    this.addTransaction("SYSTEM_REWARD", "Miner_Sam", 50.0);
    await this.minePendingTransactions("Miner_Sam");

    // Block 2
    this.addTransaction("Miner_Sam", "Alice", 30.0);
    await this.minePendingTransactions("Miner_Sam");

    // Block 3
    this.addTransaction("Alice", "Bob", 12.5);
    await this.minePendingTransactions("Miner_Sam");
  }

  async computeBlockHash(block) {
    const payload = {
      data: block.data,
      index: block.index,
      merkle_root: await computeMerkleRootJs(block.data),
      nonce: block.nonce,
      previous_hash: block.previous_hash,
      timestamp: block.timestamp,
    };
    return sha256(deterministicJson(payload));
  }

  async mineBlock(block, onProgress = null) {
    const target = "0".repeat(this.difficulty);
    block.nonce = 0;
    let attempts = 0;
    const startTime = performance.now();

    while (true) {
      attempts++;
      const candidate = await this.computeBlockHash(block);
      if (onProgress && attempts % 100 === 0) {
        onProgress(block.nonce, candidate, attempts);
      }
      if (candidate.startsWith(target)) {
        block.hash = candidate;
        block.merkle_root = await computeMerkleRootJs(block.data);
        break;
      }
      block.nonce++;
      if (attempts % 400 === 0) {
        await new Promise((r) => setTimeout(r, 0));
      }
    }
    const elapsed = (performance.now() - startTime) / 1000;
    return { hash: block.hash, attempts, elapsed };
  }

  getBalance(address) {
    let bal = 0;
    for (const b of this.chain) {
      const txs = Array.isArray(b.data) ? b.data : [b.data];
      for (const tx of txs) {
        if (typeof tx === "object" && tx !== null) {
          if (tx.sender === address) bal -= Number(tx.amount || 0);
          if (tx.receiver === address) bal += Number(tx.amount || 0);
        }
      }
    }
    for (const tx of this.pendingTransactions) {
      if (tx.sender === address) bal -= Number(tx.amount || 0);
      if (tx.receiver === address) bal += Number(tx.amount || 0);
    }
    return bal;
  }

  addTransaction(sender, receiver, amount) {
    if (amount <= 0) return false;
    if (sender !== "SYSTEM_REWARD") {
      const avail = this.getBalance(sender);
      if (avail < amount) return false;
    }
    this.pendingTransactions.push({ sender, receiver, amount: Number(amount) });
    return true;
  }

  async minePendingTransactions(minerAddress, onProgress = null) {
    const coinbase = {
      sender: "SYSTEM_REWARD",
      receiver: minerAddress,
      amount: this.miningReward,
    };
    const txs = [coinbase, ...this.pendingTransactions];
    this.pendingTransactions = [];

    const prevBlock = this.chain[this.chain.length - 1];
    const newBlock = {
      index: this.chain.length,
      timestamp: Date.now() / 1000,
      data: txs,
      previous_hash: prevBlock ? prevBlock.hash : "0",
      nonce: 0,
      hash: "",
      merkle_root: await computeMerkleRootJs(txs),
    };

    const res = await this.mineBlock(newBlock, onProgress);
    this.chain.push(newBlock);
    return { block: newBlock, ...res };
  }

  async auditChain() {
    const target = "0".repeat(this.difficulty);
    for (let i = 0; i < this.chain.length; i++) {
      const curr = this.chain[i];
      const recomputed = await this.computeBlockHash(curr);

      if (recomputed !== curr.hash) {
        return {
          isValid: false,
          reason: `Check 1 Failed (Stored Hash Integrity) at Block #${curr.index}: stored hash does not match content.`,
          failingIndex: curr.index,
          checkType: 1,
        };
      }

      if (i > 0) {
        const prev = this.chain[i - 1];
        if (curr.previous_hash !== prev.hash) {
          return {
            isValid: false,
            reason: `Check 2 Failed (Previous-Hash Linkage) at Block #${curr.index}: previous_hash does not match Block #${prev.index} hash.`,
            failingIndex: curr.index,
            checkType: 2,
          };
        }
      }

      if (!curr.hash.startsWith(target)) {
        return {
          isValid: false,
          reason: `Target Check Failed at Block #${curr.index}: Hash does not meet difficulty target.`,
          failingIndex: curr.index,
          checkType: 3,
        };
      }
    }
    return { isValid: true, reason: "Blockchain is valid and cryptographically linked." };
  }

  async serializeState() {
    const audit = await this.auditChain();
    const accounts = ["Miner_Sam", "Alice", "Bob", "Charlie", "Dave", "Eve"];
    const balances = {};
    for (const a of accounts) balances[a] = this.getBalance(a);

    const serializedChain = [];
    for (let i = 0; i < this.chain.length; i++) {
      const b = this.chain[i];
      const recomputed = await this.computeBlockHash(b);
      serializedChain.push({
        index: b.index,
        timestamp: b.timestamp,
        data: b.data,
        previous_hash: b.previous_hash,
        nonce: b.nonce,
        hash: b.hash,
        merkle_root: b.merkle_root || (await computeMerkleRootJs(b.data)),
        recomputed_hash: recomputed,
        is_stored_hash_valid: recomputed === b.hash,
        is_link_valid: i === 0 ? b.previous_hash === "0" : b.previous_hash === this.chain[i - 1].hash,
        meets_target: b.hash.startsWith("0".repeat(this.difficulty)),
      });
    }

    return {
      difficulty: this.difficulty,
      mining_reward: this.miningReward,
      chain_length: this.chain.length,
      is_valid: audit.isValid,
      validation_reason: audit.reason,
      balances,
      pending_transactions: this.pendingTransactions,
      chain: serializedChain,
    };
  }
}

const fallbackBlockchain = new InBrowserBlockchain(3, 50.0);

/* ==========================================================================
   Backend API Bridge & Fallback Synchronization
   ========================================================================== */

async function fetchState() {
  try {
    const res = await fetch("/api/chain", { cache: "no-store" });
    if (!res.ok) throw new Error("API not ok");
    const data = await res.json();
    isBackendConnected = true;
    blockchainState = data;
    updateConnectionStatus(true);
    renderApp();
  } catch (err) {
    // Fall back to in-browser engine
    isBackendConnected = false;
    updateConnectionStatus(false);
    if (!blockchainState) {
      await fallbackBlockchain.init();
    }
    blockchainState = await fallbackBlockchain.serializeState();
    renderApp();
  }
}

function updateConnectionStatus(connected) {
  if (connected) {
    connectionStatus.className = "status-pill status-connected";
    connectionText.textContent = "Live Python REST API";
  } else {
    connectionStatus.className = "status-pill status-disconnected";
    connectionText.textContent = "In-Browser WebCrypto Mode";
  }
}

/* ==========================================================================
   Rendering View Logic
   ========================================================================== */

function renderApp() {
  if (!blockchainState) return;

  // 1. Metrics Ribbon
  statHeight.textContent = blockchainState.chain_length;
  statHeightSub.textContent = `Tip: Block #${blockchainState.chain_length - 1}`;
  statDifficulty.textContent = `Difficulty ${blockchainState.difficulty}`;
  const targetZeros = "0".repeat(blockchainState.difficulty);
  const approxHashes = Math.pow(16, blockchainState.difficulty).toLocaleString();
  statTargetPrefix.textContent = `Target: prefix "${targetZeros}" (~${approxHashes} hashes)`;

  difficultySlider.value = blockchainState.difficulty;
  difficultyVal.textContent = `${blockchainState.difficulty} ("${targetZeros}")`;

  // Calculate circulating coins (50 per block)
  const totalCoins = (blockchainState.chain_length - 1) * blockchainState.mining_reward;
  statSupply.textContent = `${Math.max(0, totalCoins).toFixed(2)} COINS`;
  statMempool.textContent = `${blockchainState.pending_transactions.length} Tx`;
  mempoolBadge.textContent = `${blockchainState.pending_transactions.length} Pending`;
  blockCountBadge.textContent = `${blockchainState.chain_length} Blocks`;

  // 2. Health & Alerts
  if (blockchainState.is_valid) {
    chainHealthBadge.className = "status-pill health-valid";
    chainHealthBadge.innerHTML = `<span class="health-icon">🛡️</span><span>Chain Verified</span>`;
    validationAlert.classList.add("hidden");
  } else {
    chainHealthBadge.className = "status-pill health-invalid";
    chainHealthBadge.innerHTML = `<span class="health-icon">🚨</span><span>Integrity Compromised</span>`;
    validationAlert.classList.remove("hidden");
    alertTitle.textContent = "Cryptographic Verification Failed!";
    alertDescription.textContent = blockchainState.validation_reason;
  }

  // 3. Render Blocks Stream
  renderBlocks();

  // 4. Render Balances Grid
  renderBalances();

  // 5. Render Mempool List
  renderMempool();
}

function renderBlocks() {
  blocksContainer.innerHTML = "";

  const chain = blockchainState.chain;
  chain.forEach((block, index) => {
    // Connector Link to Previous Block
    if (index > 0) {
      const linkConnector = document.createElement("div");
      linkConnector.className = "chain-link-connector";

      const isBroken = !block.is_link_valid;
      linkConnector.innerHTML = `
        <div class="link-line ${isBroken ? "line-broken" : ""}"></div>
        <div class="link-badge ${isBroken ? "link-broken" : ""}">
          ${isBroken ? "✖ LINK SEVERED (HASH MISMATCH)" : "🔗 PREV_HASH LINKED"}
        </div>
        <div class="link-line ${isBroken ? "line-broken" : ""}"></div>
      `;
      blocksContainer.appendChild(linkConnector);
    }

    // Block Card
    const card = document.createElement("div");
    let cardClass = "block-card";
    let tagHtml = "";

    if (block.index === 0) {
      tagHtml = `<span class="block-tag tag-genesis">Genesis</span>`;
      cardClass += " valid-card";
    } else if (!block.is_stored_hash_valid) {
      tagHtml = `<span class="block-tag tag-tampered">Check 1: Tampered Data</span>`;
      cardClass += " tampered-card";
    } else if (!block.is_link_valid) {
      tagHtml = `<span class="block-tag tag-broken-link">Check 2: Link Broken</span>`;
      cardClass += " broken-link-card";
    } else {
      tagHtml = `<span class="block-tag tag-valid">Valid & Mined</span>`;
      cardClass += " valid-card";
    }

    card.className = cardClass;

    // Formatting Hash with highlighted prefix
    const diff = blockchainState.difficulty;
    const targetZeros = "0".repeat(diff);
    let hashFormatted = block.hash;
    if (block.hash.startsWith(targetZeros)) {
      hashFormatted = `<span class="hash-prefix">${targetZeros}</span>${block.hash.slice(diff)}`;
    }

    card.innerHTML = `
      <div class="block-header">
        <div class="block-index-title">
          <span>Block #${block.index}</span>
          ${tagHtml}
        </div>
        <div class="block-actions">
          <button class="btn btn-secondary btn-xs btn-inspect-merkle" data-index="${block.index}">
            🌳 Merkle Tree
          </button>
          <button class="btn btn-secondary btn-xs btn-tamper-block" data-index="${block.index}">
            ✏️ Edit Payload
          </button>
          <button class="btn btn-primary btn-xs btn-remine-block" data-index="${block.index}">
            🔨 Re-mine
          </button>
        </div>
      </div>

      <div class="block-grid">
        <div class="field-group">
          <span class="field-label">Timestamp</span>
          <span class="field-value">${new Date(block.timestamp * 1000).toLocaleTimeString()} (${block.timestamp.toFixed(2)})</span>
        </div>

        <div class="field-group">
          <span class="field-label">Proof-of-Work Nonce</span>
          <span class="field-value field-mono">${Number(block.nonce).toLocaleString()}</span>
        </div>

        <div class="field-group" style="grid-column: 1 / -1;">
          <span class="field-label">Previous Block Hash</span>
          <span class="field-value field-mono">${block.previous_hash}</span>
        </div>

        <div class="field-group" style="grid-column: 1 / -1;">
          <span class="field-label">Mined Block Hash</span>
          <span class="field-value field-mono">${hashFormatted}</span>
          ${!block.is_stored_hash_valid
        ? `<div style="font-size:0.75rem; color:#fca5a5; margin-top:0.25rem;">
                   ⚠️ Stored hash does not match recomputed hash: <span style="font-family:var(--font-mono);">${block.recomputed_hash.slice(0, 20)}...</span>
                 </div>`
        : ""
      }
        </div>

        <div class="field-group" style="grid-column: 1 / -1;">
          <span class="field-label">Merkle Tree Root</span>
          <span class="field-value field-mono" style="color:var(--accent-purple);">${block.merkle_root || "N/A"}</span>
        </div>
      </div>

      <div class="block-txs-wrap">
        <div class="txs-header">
          <span>Payload Content</span>
          <span>${Array.isArray(block.data) ? block.data.length + " Transaction(s)" : "Raw Payload"}</span>
        </div>
        ${renderBlockDataHtml(block.data)}
      </div>
    `;

    blocksContainer.appendChild(card);
  });

  // Attach event listeners to card buttons
  document.querySelectorAll(".btn-inspect-merkle").forEach((btn) => {
    btn.addEventListener("click", () => openMerkleModal(Number(btn.dataset.index)));
  });

  document.querySelectorAll(".btn-tamper-block").forEach((btn) => {
    btn.addEventListener("click", () => openTamperModal(Number(btn.dataset.index)));
  });

  document.querySelectorAll(".btn-remine-block").forEach((btn) => {
    btn.addEventListener("click", () => handleRemineBlock(Number(btn.dataset.index)));
  });
}

function renderBlockDataHtml(data) {
  if (Array.isArray(data)) {
    return data
      .map((tx) => {
        const isCoinbase = tx.sender === "SYSTEM_REWARD";
        return `
        <div class="tx-row ${isCoinbase ? "tx-coinbase" : ""}">
          <span>
            <strong>${tx.sender}</strong>
            <span class="tx-arrow">&rarr;</span>
            <strong>${tx.receiver}</strong>
          </span>
          <span class="tx-amt">${Number(tx.amount).toFixed(2)} COINS</span>
        </div>
      `;
      })
      .join("");
  }
  return `<div class="tx-row"><span>${typeof data === "string" ? data : JSON.stringify(data)}</span></div>`;
}

function renderBalances() {
  balancesGrid.innerHTML = "";
  const balances = blockchainState.balances || {};
  for (const [acc, bal] of Object.entries(balances)) {
    const item = document.createElement("div");
    item.className = "balance-item";
    item.innerHTML = `
      <span class="balance-name">${acc}</span>
      <span class="balance-amt">${Number(bal).toFixed(2)}</span>
    `;
    balancesGrid.appendChild(item);
  }
}

function renderMempool() {
  mempoolList.innerHTML = "";
  const pool = blockchainState.pending_transactions || [];
  if (pool.length === 0) {
    mempoolList.innerHTML = `<div class="empty-mempool">No transactions in mempool</div>`;
    return;
  }
  pool.forEach((tx) => {
    const div = document.createElement("div");
    div.className = "mempool-item";
    div.innerHTML = `
      <span>${tx.sender} &rarr; ${tx.receiver}</span>
      <strong>${Number(tx.amount).toFixed(2)}</strong>
    `;
    mempoolList.appendChild(div);
  });
}

/* ==========================================================================
   User Interactions & Actions
   ========================================================================== */

// 1. Mine Next Block
async function handleMineBlock() {
  if (isMiningInProgress) return;
  isMiningInProgress = true;
  btnMineBlock.disabled = true;
  miningStatusBadge.textContent = "Mining (Proof-of-Work)...";
  miningStatusBadge.style.color = "var(--accent-cyan)";

  const miner = minerSelect.value;
  const diff = Number(difficultySlider.value);
  const targetPrefix = "0".repeat(diff);

  const startTime = performance.now();
  let fakeNonce = 0;
  const timerInterval = setInterval(() => {
    fakeNonce += 250;
    const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
    liveNonce.textContent = fakeNonce.toLocaleString();
    liveAttempts.textContent = fakeNonce.toLocaleString();
    liveTimer.textContent = `${elapsed}s`;
    liveHashRate.textContent = `${Math.round(fakeNonce / Math.max(0.1, elapsed)).toLocaleString()} H/s`;
  }, 50);

  try {
    if (isBackendConnected) {
      const res = await fetch("/api/mine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ miner_address: miner, difficulty: diff }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Mining failed");

      clearInterval(timerInterval);
      const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
      liveNonce.textContent = Number(data.block.nonce).toLocaleString();
      liveHash.textContent = data.block.hash;
      liveAttempts.textContent = Number(data.attempts).toLocaleString();
      liveTimer.textContent = `${elapsed}s`;
      liveHashRate.textContent = `${Math.round(data.attempts / Math.max(0.1, elapsed)).toLocaleString()} H/s`;

      showToast(`Block #${data.block.index} mined in ${elapsed}s!`, "success");
      await fetchState();
    } else {
      fallbackBlockchain.difficulty = diff;
      const res = await fallbackBlockchain.minePendingTransactions(miner, (nonce, cand, atts) => {
        liveNonce.textContent = nonce.toLocaleString();
        liveHash.textContent = cand;
      });
      clearInterval(timerInterval);
      const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
      liveNonce.textContent = Number(res.block.nonce).toLocaleString();
      liveHash.textContent = res.block.hash;
      liveAttempts.textContent = Number(res.attempts).toLocaleString();
      liveTimer.textContent = `${elapsed}s`;

      showToast(`Block #${res.block.index} mined in ${elapsed}s!`, "success");
      blockchainState = await fallbackBlockchain.serializeState();
      renderApp();
    }
  } catch (err) {
    clearInterval(timerInterval);
    showToast(`Mining error: ${err.message}`, "error");
  } finally {
    isMiningInProgress = false;
    btnMineBlock.disabled = false;
    miningStatusBadge.textContent = "Ready";
    miningStatusBadge.style.color = "var(--text-muted)";
  }
}

// 2. Add Transaction to Mempool
async function handleAddTransaction(e) {
  e.preventDefault();
  const sender = txSender.value;
  const receiver = txReceiver.value;
  const amount = Number(txAmount.value);

  if (sender === receiver) {
    showToast("Sender and receiver cannot be identical.", "error");
    return;
  }

  try {
    if (isBackendConnected) {
      const res = await fetch("/api/transaction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender, receiver, amount }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to add transaction");
      showToast(data.message, "success");
      await fetchState();
    } else {
      const ok = fallbackBlockchain.addTransaction(sender, receiver, amount);
      if (!ok) {
        const avail = fallbackBlockchain.getBalance(sender);
        throw new Error(`Insufficient funds for ${sender}. Available: ${avail.toFixed(2)}`);
      }
      showToast(`Queued ${amount} coins from ${sender} to ${receiver}`, "success");
      blockchainState = await fallbackBlockchain.serializeState();
      renderApp();
    }
    txAmount.value = "10.0";
  } catch (err) {
    showToast(err.message, "error");
  }
}

// 3. Clear Mempool
async function handleClearMempool() {
  if (isBackendConnected) {
    await fetchState();
  } else {
    fallbackBlockchain.pendingTransactions = [];
    blockchainState = await fallbackBlockchain.serializeState();
    renderApp();
  }
  showToast("Mempool cleared", "info");
}

// 4. Audit Chain Integrity
async function handleAuditChain() {
  btnAuditChain.disabled = true;
  try {
    await fetchState();
    if (blockchainState.is_valid) {
      showToast("Chain Audit Passed: All hashes & links 100% verified!", "success");
    } else {
      showToast(`Chain Audit Failed: ${blockchainState.validation_reason}`, "error");
    }
  } finally {
    btnAuditChain.disabled = false;
  }
}

// 5. Reset Blockchain
async function handleResetChain() {
  if (isBackendConnected) {
    await fetch("/api/reset", { method: "POST" });
    await fetchState();
  } else {
    await fallbackBlockchain.init();
    blockchainState = await fallbackBlockchain.serializeState();
    renderApp();
  }
  btnRemineBlock1.disabled = true;
  btnRepairChain.disabled = true;
  tamperNotes.innerHTML = `<strong>Status:</strong> Blockchain reset to clean verified state.`;
  showToast("Blockchain reset to initial state.", "info");
}

// 6. Tamper Simulation Lab (Check 1 & Check 2 Cascade)
async function handleTamperPreset() {
  const tamperedData = [
    { sender: "SYSTEM_REWARD", receiver: "Miner_Sam", amount: 50.0 },
    { sender: "Alice", receiver: "Eve", amount: 1000.0 }, // Injected illegal transfer!
  ];

  if (isBackendConnected) {
    await fetch("/api/tamper", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: 1, data: tamperedData }),
    });
    await fetchState();
  } else {
    fallbackBlockchain.chain[1].data = tamperedData;
    blockchainState = await fallbackBlockchain.serializeState();
    renderApp();
  }

  btnRemineBlock1.disabled = false;
  tamperNotes.innerHTML = `
    <span style="color:#fca5a5;"><strong>[PHASE 1 TRIGGERED] Check 1 Failed at Block #1:</strong></span><br>
    The transaction data inside Block #1 was altered directly to send 1,000 coins to Eve. 
    Notice that Block #1's stored hash no longer matches its recomputed hash!
    <br><br>
    Next step: Click <strong>"2. Re-mine Block #1 Only"</strong> to see what happens when the attacker re-mines Block #1.
  `;
  showToast("Block #1 data tampered! Check 1 failure triggered.", "error");
}

async function handleRemineBlock1() {
  await handleRemineBlock(1);
  btnRemineBlock1.disabled = true;
  btnRepairChain.disabled = false;

  tamperNotes.innerHTML = `
    <span style="color:#fbbf24;"><strong>[PHASE 2 TRIGGERED] Check 2 Cascading Failure at Block #2:</strong></span><br>
    The attacker re-mined Block #1, so Block #1 now has a valid hash matching its tampered data. 
    <strong>BUT Block #2's previous_hash still points to Block #1's old hash!</strong>
    The cryptographic link is severed (shown in red above).
    <br><br>
    Next step: Click <strong>"3. Repair Entire Remaining Chain"</strong> to witness re-mining every subsequent block.
  `;
}

async function handleRepairChain() {
  btnRepairChain.disabled = true;
  showToast("Re-mining all subsequent blocks to restore chain...", "info");

  if (isBackendConnected) {
    const res = await fetch("/api/repair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: 1 }),
    });
    const data = await res.json();
    showToast(data.message, "success");
    await fetchState();
  } else {
    for (let i = 1; i < fallbackBlockchain.chain.length; i++) {
      fallbackBlockchain.chain[i].previous_hash = fallbackBlockchain.chain[i - 1].hash;
      await fallbackBlockchain.mineBlock(fallbackBlockchain.chain[i]);
    }
    blockchainState = await fallbackBlockchain.serializeState();
    renderApp();
    showToast("Chain successfully repaired!", "success");
  }

  tamperNotes.innerHTML = `
    <span style="color:#34d399;"><strong>[CHAIN REPAIRED]</strong></span><br>
    The chain is valid again, but the attacker had to re-compute Proof-of-Work for Block #1, Block #2, Block #3, etc.
    In real distributed blockchains (Bitcoin), this is computationally impossible because the honest network is always extending the valid chain faster!
  `;
}

async function handleRemineBlock(blockIndex) {
  showToast(`Re-mining Block #${blockIndex}...`, "info");
  if (isBackendConnected) {
    const res = await fetch("/api/remine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: blockIndex }),
    });
    const data = await res.json();
    showToast(data.message, "success");
    await fetchState();
  } else {
    await fallbackBlockchain.mineBlock(fallbackBlockchain.chain[blockIndex]);
    blockchainState = await fallbackBlockchain.serializeState();
    renderApp();
    showToast(`Block #${blockIndex} re-mined!`, "success");
  }
}

// 7. Modals: Merkle Tree Inspector
function openMerkleModal(blockIndex) {
  const block = blockchainState.chain[blockIndex];
  if (!block) return;

  document.getElementById("merkleModalTitle").textContent = `Block #${block.index} Merkle Tree Inspector`;
  merkleTreeCanvas.innerHTML = "";

  const txs = Array.isArray(block.data) ? block.data : [block.data];

  // Build tree levels representation
  const levelLeaves = txs.map((tx, idx) => ({
    label: `Tx ${idx + 1}`,
    content: typeof tx === "object" ? `${tx.sender || "?"} &rarr; ${tx.receiver || "?"} (${tx.amount || 0})` : String(tx),
  }));

  const rootDiv = document.createElement("div");
  rootDiv.className = "merkle-level";
  rootDiv.innerHTML = `
    <div class="merkle-node root-node">
      <div class="merkle-node-label">MERKLE ROOT HASH</div>
      <div>${(block.merkle_root || "").slice(0, 16)}...</div>
    </div>
  `;
  merkleTreeCanvas.appendChild(rootDiv);

  const leavesDiv = document.createElement("div");
  leavesDiv.className = "merkle-level";
  levelLeaves.forEach((leaf) => {
    const node = document.createElement("div");
    node.className = "merkle-node leaf-node";
    node.innerHTML = `
      <div class="merkle-node-label">${leaf.label}</div>
      <div>${leaf.content}</div>
    `;
    leavesDiv.appendChild(node);
  });
  merkleTreeCanvas.appendChild(leavesDiv);

  merkleModal.showModal();
}

function openTamperModal(blockIndex) {
  currentTamperedBlockIndex = blockIndex;
  const block = blockchainState.chain[blockIndex];
  tamperModalTitle.textContent = `Edit Block #${blockIndex} Payload`;
  tamperPayloadJson.value = JSON.stringify(block.data, null, 2);
  tamperModal.showModal();
}

async function handleConfirmTamper() {
  try {
    const parsedData = JSON.parse(tamperPayloadJson.value);
    if (isBackendConnected) {
      await fetch("/api/tamper", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ index: currentTamperedBlockIndex, data: parsedData }),
      });
      await fetchState();
    } else {
      fallbackBlockchain.chain[currentTamperedBlockIndex].data = parsedData;
      blockchainState = await fallbackBlockchain.serializeState();
      renderApp();
    }
    tamperModal.close();
    showToast(`Block #${currentTamperedBlockIndex} payload updated!`, "error");
  } catch (err) {
    showToast("Invalid JSON payload syntax", "error");
  }
}

// Toast helper
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️"}</span>
    <span>${message}</span>
  `;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

/* ==========================================================================
   Initialization
   ========================================================================== */

function initEventListeners() {
  btnMineBlock.addEventListener("click", handleMineBlock);
  txForm.addEventListener("submit", handleAddTransaction);
  btnClearMempool.addEventListener("click", handleClearMempool);
  btnAuditChain.addEventListener("click", handleAuditChain);
  btnResetChain.addEventListener("click", handleResetChain);
  btnDismissAlert.addEventListener("click", () => validationAlert.classList.add("hidden"));

  btnTamperPreset.addEventListener("click", handleTamperPreset);
  btnRemineBlock1.addEventListener("click", handleRemineBlock1);
  btnRepairChain.addEventListener("click", handleRepairChain);

  btnCloseMerkleModal.addEventListener("click", () => merkleModal.close());
  btnCloseTamperModal.addEventListener("click", () => tamperModal.close());
  btnCancelTamper.addEventListener("click", () => tamperModal.close());
  btnConfirmTamper.addEventListener("click", handleConfirmTamper);

  difficultySlider.addEventListener("input", (e) => {
    const val = e.target.value;
    const zeros = "0".repeat(val);
    difficultyVal.textContent = `${val} ("${zeros}")`;
  });

  difficultySlider.addEventListener("change", async (e) => {
    const val = Number(e.target.value);
    if (isBackendConnected) {
      await fetch("/api/difficulty", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ difficulty: val }),
      });
      await fetchState();
    } else {
      fallbackBlockchain.difficulty = val;
      blockchainState = await fallbackBlockchain.serializeState();
      renderApp();
    }
    showToast(`Difficulty set to ${val}`, "info");
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  initEventListeners();
  await fetchState();
  // Poll server state every 3 seconds to keep tabs synchronized
  setInterval(fetchState, 3000);
});
