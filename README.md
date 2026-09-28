# Mini-Blockchain from Scratch

A clean, modular educational implementation of a blockchain, Proof-of-Work (PoW) consensus, and state-machine ledger built using **Python 3 standard library modules only** (`hashlib`, `time`, `json`, `unittest`).

---

## 1. Project Architecture & Components

```
+-------------------------------------------------------------+
|                      GENESIS BLOCK (#0)                     |
|  Index: 0 | PrevHash: "0" | Nonce: 272065                   |
|  Merkle Root: f106434e... | Hash: 0000e134...               |
+------------------------------+------------------------------+
                               |
                               | (previous_hash points to Block #0 Hash)
                               v
+-------------------------------------------------------------+
|                          BLOCK #1                           |
|  Index: 1 | PrevHash: 0000e134... | Nonce: 16284            |
|  Transactions / Payload: {"sender": "Alice", ...}           |
|  Merkle Root: b9d5f900... | Hash: 00009e5b...               |
+------------------------------+------------------------------+
                               |
                               | (previous_hash points to Block #1 Hash)
                               v
+-------------------------------------------------------------+
|                          BLOCK #2                           |
|  Index: 2 | PrevHash: 00009e5b... | Nonce: 23346            |
|  Transactions: [Coinbase + Miner_Sam -> Alice + ...]        |
|  Merkle Root: 6724a606... | Hash: 00006018...               |
+-------------------------------------------------------------+
```

### Core Primitives
1. **Deterministic Serialization**: Block data, headers, and transaction dictionaries are normalized using `json.dumps(..., sort_keys=True)` before hashing.
2. **Binary Merkle Trees**: Payloads and transaction arrays are paired and hashed recursively into a single 32-byte `merkle_root` digest (odd leaves are duplicated per Bitcoin standard).
3. **Proof-of-Work (PoW)**: Miners vary a numeric `nonce` until the block's SHA-256 hash has $d$ leading hexadecimal zeros (`"0" * difficulty`).
4. **Dual-Phase Audit (`is_chain_valid`)**:
   - **Check 1 (Stored Hash Integrity)**: Verifies $\text{compute\_hash}(\text{block}) == \text{block.hash}$ (catches content tampering).
   - **Check 2 (Previous-Hash Linkage)**: Verifies $\text{current.previous\_hash} == \text{previous.hash}$ (catches historical rewrites).
5. **Mempool & Coinbase Rewards**:
   - Miners receive newly minted currency (`SYSTEM_REWARD -> miner_address`).
   - Senders can only spend confirmed + available unconfirmed coins; double-spending and overspending attempts are rejected.

---

## 2. Theoretical Concepts & Deep Dive

### A. How `previous_hash` Turns Independent Blocks into a Linked Ledger
A list of standalone records has no inherent chronological integrity; an adversary could freely delete, re-order, or inject records without changing any record's internal data.

By embedding the exact cryptographic hash of block $N-1$ into the header of block $N$, block $N$ forms a permanent, tamper-evident commitment to the entire history before it:
$$\text{Hash}_N = \text{SHA256}(\text{Index}_N, \text{Timestamp}_N, \text{Data}_N, \mathbf{Hash_{N-1}}, \text{Nonce}_N, \text{MerkleRoot}_N)$$
Because $\text{Hash}_{N-1}$ is an input to $\text{Hash}_N$, any modification to block $N-1$ produces a completely different value for $\text{Hash}_{N-1}$. This immediately invalidates the link stored inside block $N$, which in turn changes $\text{Hash}_N$, breaking block $N+1$, and cascading down to the tip of the chain. This recursive parent-pointer dependency is what converts isolated data snapshots into an append-only, chronologically ordered Merkle chain.

---

### B. The Avalanche Effect: Why a Single-Character Edit Is Instantly Detectable
Cryptographic hash functions like SHA-256 are engineered with a strict mathematical property known as the **avalanche effect** (or strict avalanche criterion).
- When a single bit in the input changes (e.g., modifying an amount from `50.0` to `50.1` or swapping `"Bob"` to `"Eve"`), the internal non-linear bitwise operations, modular additions, and compression rounds flip approximately **50% of the output bits** pseudo-randomly.
- SHA-256 outputs a 256-bit (64 hex digit) digest. Even a one-character variation transforms the entire digest into an unrecognizable, completely decorrelated hexadecimal string.
- Because the stored `block.hash` must strictly equal the recomputed hash, any alteration—down to a single space or punctuation mark—causes an immediate, glaring mismatch.

---

### C. Why Raising Difficulty Increases Mining Time Exponentially
In Proof-of-Work, a block is considered valid if and only if:
$$\text{Hash}(\text{Block}) < \text{Target}$$
Represented in hexadecimal notation, a difficulty of $d$ requires the hash string to begin with $d$ consecutive zero characters (`"0" * d`).

1. **Probability per Attempt**:
   Because SHA-256 acts as a uniform random oracle, each hexadecimal character position has 16 equally likely outcomes (`0`–`9`, `a`–`f`).
   The probability that a random hash starts with $d$ zeros is:
   $$P(\text{success}) = \left(\frac{1}{16}\right)^d = 16^{-d}$$

2. **Expected Hash Attempts**:
   The number of hashing attempts required to find a valid nonce follows a geometric distribution with expectation:
   $$\mathbb{E}[\text{Attempts}] = 16^d$$

3. **Difficulty Scaling Comparison**:
   | Difficulty ($d$) | Target Prefix | Expected Hashes ($16^d$) | Approximate CPU Time |
   | :--- | :--- | :--- | :--- |
   | **1** | `0` | $16^1 = 16$ | $< 0.001$ seconds |
   | **2** | `00` | $16^2 = 256$ | $\approx 0.002$ seconds |
   | **3** | `000` | $16^3 = 4,096$ | $\approx 0.03$ seconds |
   | **4** (Default) | `0000` | $16^4 = 65,536$ | $\approx 0.3 - 1.5$ seconds |
   | **5** | `00000` | $16^5 = 1,048,576$ | $\approx 5 - 15$ seconds |
   | **6** | `000000` | $16^6 = 16,777,216$ | $\approx 1.5 - 3$ minutes |

Each increment of 1 in difficulty multiplies the computational search space by a factor of **16** ($2^4$), resulting in pure exponential scaling.

---

### D. Dual-Phase Validation: Check 1 vs. Check 2
`Blockchain.is_chain_valid()` enforces two distinct and complementary audit passes for every block:

| Validation Rule | Logic Checked | What It Catches (Unique Failure Mode) | What It Cannot Catch |
| :--- | :--- | :--- | :--- |
| **Check 1: Stored Hash Integrity** | $\text{compute\_hash}(\text{block}) == \text{block.hash}$ | **Intra-block payload tampering.** Catches an attacker who edits transaction data, timestamps, or nonce inside a block without re-mining. | If an attacker edits a block *and* successfully re-mines it, Check 1 will **pass** on that block! |
| **Check 2: Previous-Hash Linkage** | $\text{current.previous\_hash} == \text{previous.hash}$ | **Inter-block continuity and sequence tampering.** Catches block deletions, block insertions, re-ordering, or when an attacker re-mines a tampered past block without re-mining subsequent blocks. | If an attacker modifies the data of the *very last* block and re-mines it, Check 2 will not catch it (since no subsequent block points to it yet); Check 1 catches that. |

---

## 3. Web Frontend & Interactive Studio

The project includes an interactive web frontend:

```bash
python server.py
```

Open **`http://localhost:8000`** in any web browser.

### Key Frontend Features:
- **Live Block Stream**: Visual cards displaying block height, nonces, timestamps, payload transactions, and Merkle roots.
- **Cryptographic Linkage Visualization**: Glowing connectors between blocks that turn red with a `LINK SEVERED` alert when a block's `previous_hash` does not match.
- **Real-Time PoW Mining Studio**: Interactive difficulty slider (1 to 5) with a live mining gauge tracking nonce attempts, candidate hashes, elapsed time, and hash rate (H/s).
- **Mempool & Wallet Balances**: Transfer coins with balance verification, queue transactions, and mine blocks with Coinbase rewards.
- **Tamper & Cascading Failure Lab**:
  - **Step 1 (Tamper)**: Directly alters Block #1's payload to trigger **Check 1 Failure (Stored Hash Integrity)**.
  - **Step 2 (Re-mine Block #1 Only)**: Re-mines Block #1 to satisfy Check 1, but severs the link to Block #2, triggering **Check 2 Failure (Previous-Hash Linkage)**.
  - **Step 3 (Repair Chain)**: Re-mines all subsequent blocks to restore full validity, demonstrating the exponential computational cost of rewriting history.
- **Binary Merkle Tree Inspector**: Click "Merkle Tree" on any block to view an interactive visual breakdown of transaction hashes up to the Merkle Root.
- **Dual Mode**: Can connect directly to the Python REST API server or run 100% offline in standalone mode using the browser's built-in Web Cryptography API (`crypto.subtle`).

---

## 4. How to Run via CLI

### Main Terminal Demonstration
```bash
python mini_blockchain.py
```

### Automated Unit Tests
Run the comprehensive test suite with Python's built-in test runner:
```bash
python -m unittest test_blockchain.py -v
```
All 7 unit tests cover Genesis initialization, Proof of Work, Merkle tree avalanche effect, tamper detection, and balance auditing.
# Decodelabs_tasks_01
