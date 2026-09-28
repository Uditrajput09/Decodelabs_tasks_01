"""
Mini-Blockchain from Scratch
============================
An educational, production-style implementation of a blockchain built with
Python 3 standard library modules only (hashlib, time, json).

Features:
- Deterministic SHA-256 block hashing
- Binary Merkle Tree root calculation for transactions
- Proof-of-Work (PoW) consensus with difficulty targeting
- Dual-phase integrity & linkage validation
- Mempool (unconfirmed transaction pool) & Coinbase mining rewards
- State ledger balance verification (double-spending protection)
- Tamper detection and cascading failure demonstration
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Union


class ValidationResult(tuple):
    """
    Validation result wrapper that behaves as a tuple (is_valid: bool, reason: str),
    evaluates directly as a boolean in conditional statements, and prints cleanly.
    """

    def __new__(cls, is_valid: bool, reason: str = "") -> ValidationResult:
        return super().__new__(cls, (is_valid, reason))

    @property
    def is_valid(self) -> bool:
        """Return boolean validity flag."""
        return self[0]

    @property
    def reason(self) -> str:
        """Return diagnostic explanation for validation outcome."""
        return self[1]

    def __bool__(self) -> bool:
        return self[0]

    def __str__(self) -> str:
        if self[0]:
            return "True (Chain is valid and verified)"
        return f"False - [Validation Failure] {self[1]}"

    def __repr__(self) -> str:
        return f"ValidationResult(is_valid={self[0]}, reason={self[1]!r})"


def compute_merkle_root(data: Any) -> str:
    """
    Calculates the binary Merkle Tree Root for a given payload or transaction list.

    If data is a string or single dictionary, its deterministic SHA-256 is returned.
    If data is a list of transactions, elements are paired and hashed recursively.
    If an iteration has an odd number of hashes, the last hash is duplicated
    (following standard Bitcoin Merkle tree construction).

    Args:
        data (Any): Single transaction, list of transactions, or raw string.

    Returns:
        str: 64-character hexadecimal Merkle root hash.
    """
    if not isinstance(data, list):
        serialized = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    if len(data) == 0:
        return hashlib.sha256(b"").hexdigest()

    current_level = [
        hashlib.sha256(json.dumps(item, sort_keys=True).encode("utf-8")).hexdigest()
        for item in data
    ]

    while len(current_level) > 1:
        if len(current_level) % 2 != 0:
            current_level.append(current_level[-1])

        next_level = []
        for i in range(0, len(current_level), 2):
            combined = (current_level[i] + current_level[i + 1]).encode("utf-8")
            next_level.append(hashlib.sha256(combined).hexdigest())
        current_level = next_level

    return current_level[0]


class Block:
    """
    Represents an individual block within the blockchain.

    Attributes:
        index (int): Position of the block in the chain (0-indexed).
        timestamp (float): Unix epoch time when the block was generated.
        data (Any): Transaction payload (dict, list of dicts, or string).
        previous_hash (str): SHA-256 digest of the preceding block.
        nonce (int): Counter incremented to satisfy Proof of Work.
        hash (str): SHA-256 digest of this block's contents.
        merkle_root (str): Merkle tree root of the block's transaction data.
    """

    def __init__(
        self,
        index: int,
        timestamp: float,
        data: Any,
        previous_hash: str,
        nonce: int = 0,
        hash_value: str = "",
        merkle_root: Optional[str] = None,
    ) -> None:
        self.index: int = index
        self.timestamp: float = timestamp
        self.data: Any = data
        self.previous_hash: str = previous_hash
        self.nonce: int = nonce
        self.hash: str = hash_value
        self.merkle_root: str = merkle_root if merkle_root is not None else compute_merkle_root(data)

    def compute_hash(self) -> str:
        """
        Calculates the SHA-256 hex digest of the block header and payload.

        Block contents are serialized deterministically using sorted JSON keys
        to guarantee that identical contents consistently produce identical hashes.

        Returns:
            str: 64-character hexadecimal SHA-256 digest.
        """
        # Re-derive merkle root in case self.data was modified
        self.merkle_root = compute_merkle_root(self.data)
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "merkle_root": self.merkle_root,
        }
        serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes block attributes into a dictionary for printing and inspection.

        Returns:
            Dict[str, Any]: Key-value representation of the block.
        """
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
            "merkle_root": self.merkle_root,
        }

    def __repr__(self) -> str:
        return f"Block(index={self.index}, hash={self.hash[:10]}..., nonce={self.nonce})"


class Blockchain:
    """
    Manages the sequential chain of blocks, consensus difficulty, and validation rules.

    Attributes:
        difficulty (int): Number of leading hex zeros required for a valid block hash.
        chain (List[Block]): Sequence of verified blocks starting from the Genesis block.
        pending_transactions (List[Dict[str, Any]]): Unconfirmed transaction mempool.
        mining_reward (float): Newly minted coin reward granted to the block miner.
    """

    def __init__(self, difficulty: int = 4, mining_reward: float = 50.0) -> None:
        """
        Initializes the blockchain and automatically mines the Genesis block.

        Args:
            difficulty (int): Mining difficulty (default 4).
            mining_reward (float): Block subsidy reward for miners (default 50.0).
        """
        self.difficulty: int = difficulty
        self.mining_reward: float = mining_reward
        self.chain: List[Block] = []
        self.pending_transactions: List[Dict[str, Any]] = []
        self.create_genesis_block()

    def create_genesis_block(self) -> Block:
        """
        Creates, mines, and records the initial block of the blockchain (index 0).

        Returns:
            Block: The mined Genesis block.
        """
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            data="Genesis Block",
            previous_hash="0",
            nonce=0,
        )
        self.mine_block(genesis_block)
        self.chain.append(genesis_block)
        return genesis_block

    def get_latest_block(self) -> Block:
        """
        Retrieves the most recently appended block in the chain.

        Returns:
            Block: The tail block of the chain.
        """
        return self.chain[-1]

    def mine_block(self, block: Block) -> Tuple[str, int, float]:
        """
        Executes Proof-of-Work (PoW) consensus algorithm.

        Iteratively increments the block's nonce until compute_hash() produces
        a digest with `self.difficulty` leading zeros.

        Args:
            block (Block): The block to be mined.

        Returns:
            Tuple[str, int, float]: (valid_hash, attempts, elapsed_seconds).
        """
        target = "0" * self.difficulty
        block.nonce = 0
        attempts = 0
        start_time = time.time()

        while True:
            attempts += 1
            candidate_hash = block.compute_hash()
            if candidate_hash.startswith(target):
                block.hash = candidate_hash
                break
            block.nonce += 1

        elapsed = time.time() - start_time
        return block.hash, attempts, elapsed

    def add_block(self, data: Any) -> Tuple[Block, int, float]:
        """
        Constructs, mines, and appends a new block referencing the latest block's hash.

        Args:
            data (Any): Transaction payload or data to record.

        Returns:
            Tuple[Block, int, float]: (newly_mined_block, attempts, elapsed_seconds).
        """
        prev_block = self.get_latest_block()
        new_block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            data=data,
            previous_hash=prev_block.hash,
            nonce=0,
        )
        _, attempts, elapsed = self.mine_block(new_block)
        self.chain.append(new_block)
        return new_block, attempts, elapsed

    def add_transaction(self, sender: str, receiver: str, amount: float) -> bool:
        """
        Validates and queues a transaction into the mempool.
        Verifies sender has sufficient balance to prevent double-spending.

        Args:
            sender (str): Sender wallet/address.
            receiver (str): Recipient wallet/address.
            amount (float): Quantity of coins to transfer.

        Returns:
            bool: True if transaction was admitted, False if rejected.
        """
        if amount <= 0:
            print(f"[REJECTED] Transaction amount must be positive ({amount}).")
            return False

        if sender != "SYSTEM_REWARD":
            available_balance = self.get_balance(sender, include_pending=True)
            if available_balance < amount:
                print(
                    f"[REJECTED] Insufficient funds for {sender}: "
                    f"available {available_balance:.2f} < requested {amount:.2f}"
                )
                return False

        tx = {"sender": sender, "receiver": receiver, "amount": amount}
        self.pending_transactions.append(tx)
        return True

    def mine_pending_transactions(self, miner_address: str) -> Tuple[Block, int, float]:
        """
        Batches pending mempool transactions, prepends a Coinbase reward transaction,
        mines the new block, and adds it to the chain.

        Args:
            miner_address (str): Address to receive the newly minted block reward.

        Returns:
            Tuple[Block, int, float]: (mined_block, attempts, elapsed_seconds).
        """
        # Prepend Coinbase (mining subsidy) transaction
        coinbase_tx = {
            "sender": "SYSTEM_REWARD",
            "receiver": miner_address,
            "amount": self.mining_reward,
        }
        block_transactions = [coinbase_tx] + self.pending_transactions
        self.pending_transactions = []  # Clear mempool

        return self.add_block(block_transactions)

    def get_balance(self, address: str, include_pending: bool = False) -> float:
        """
        Calculates coin balance by auditing confirmed blocks, optionally
        including pending mempool transactions.

        Args:
            address (str): Account address.
            include_pending (bool): If True, also factors in unconfirmed mempool transactions.

        Returns:
            float: Net coin balance.
        """
        balance = 0.0
        for block in self.chain:
            data = block.data
            txs = data if isinstance(data, list) else [data]
            for tx in txs:
                if isinstance(tx, dict):
                    if tx.get("sender") == address:
                        balance -= float(tx.get("amount", 0.0))
                    if tx.get("receiver") == address:
                        balance += float(tx.get("amount", 0.0))

        if include_pending:
            for tx in self.pending_transactions:
                if tx.get("sender") == address:
                    balance -= float(tx.get("amount", 0.0))
                if tx.get("receiver") == address:
                    balance += float(tx.get("amount", 0.0))

        return balance

    def is_chain_valid(self, verbose: bool = False) -> ValidationResult:
        """
        Audits the entire blockchain for structural, content, and PoW integrity.

        Validates:
        1. Genesis block integrity and difficulty target.
        2. Check 1 (Stored hash integrity):
           recomputed hash == block.hash (catches intra-block tampering).
        3. Check 2 (Previous hash linkage):
           block.previous_hash == previous_block.hash (catches reordering/deletion/replacement).
        4. Proof-of-Work target satisfaction for every block.

        Args:
            verbose (bool): If True, prints diagnostic output during failure.

        Returns:
            ValidationResult: Evaluates to True if valid, or False with detailed reason.
        """
        target = "0" * self.difficulty

        # Validate Genesis Block
        genesis = self.chain[0]
        if genesis.index != 0:
            msg = f"Check 1 Failed: Genesis block index is {genesis.index}, expected 0."
            if verbose:
                print(f"[ERROR] {msg}")
            return ValidationResult(False, msg)

        if genesis.previous_hash != "0":
            msg = f"Check 2 Failed: Genesis previous_hash is '{genesis.previous_hash}', expected '0'."
            if verbose:
                print(f"[ERROR] {msg}")
            return ValidationResult(False, msg)

        if genesis.compute_hash() != genesis.hash:
            msg = (
                f"Check 1 Failed (Stored Hash Integrity): Genesis block tampered! "
                f"Stored '{genesis.hash}' != Recomputed '{genesis.compute_hash()}'."
            )
            if verbose:
                print(f"[ERROR] {msg}")
            return ValidationResult(False, msg)

        if not genesis.hash.startswith(target):
            msg = (
                f"Target Check Failed: Genesis block hash '{genesis.hash}' "
                f"does not satisfy difficulty {self.difficulty} (target '{target}')."
            )
            if verbose:
                print(f"[ERROR] {msg}")
            return ValidationResult(False, msg)

        # Validate Sequential Blocks
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            # Check 1: Stored hash integrity (catches tampering of block data/metadata)
            recomputed = current.compute_hash()
            if recomputed != current.hash:
                msg = (
                    f"Check 1 Failed (Stored Hash Integrity) at Block {current.index}: "
                    f"Stored hash '{current.hash}' does not match recomputed hash '{recomputed}'. "
                    f"[Cause: Payload or block attributes were altered without matching hash update]"
                )
                if verbose:
                    print(f"[ERROR] {msg}")
                return ValidationResult(False, msg)

            # Check 2: Previous hash linkage (catches reordering, deletions, or replaced blocks)
            if current.previous_hash != previous.hash:
                msg = (
                    f"Check 2 Failed (Previous-Hash Linkage) at Block {current.index}: "
                    f"Block {current.index} points to previous_hash '{current.previous_hash}', "
                    f"but Block {previous.index} has hash '{previous.hash}'. "
                    f"[Cause: Blockchain link severed; preceding block was modified or replaced]"
                )
                if verbose:
                    print(f"[ERROR] {msg}")
                return ValidationResult(False, msg)

            # Check Proof of Work difficulty target
            if not current.hash.startswith(target):
                msg = (
                    f"Target Check Failed at Block {current.index}: "
                    f"Hash '{current.hash}' does not satisfy difficulty target '{target}'."
                )
                if verbose:
                    print(f"[ERROR] {msg}")
                return ValidationResult(False, msg)

        return ValidationResult(True, "Blockchain is valid and cryptographically linked.")


def print_block_summary(
    block: Block,
    attempts: Optional[int] = None,
    elapsed: Optional[float] = None,
) -> None:
    """
    Prints a clean, wrap-safe formatted card for a mined block.
    Uses open borders and clean indentation to prevent terminal line overflows
    in standard 80-column consoles.
    """
    sep = "=" * 74
    print(sep)
    title = f"BLOCK #{block.index}" + (" (GENESIS BLOCK)" if block.index == 0 else "")
    print(f"  {title}")
    print("-" * 74)
    print(f"  Timestamp   : {block.timestamp:.4f}")
    
    # Format payload cleanly
    if isinstance(block.data, list):
        print(f"  Transactions: {len(block.data)} item(s)")
        for idx, tx in enumerate(block.data, 1):
            print(f"    [{idx}] {json.dumps(tx)}")
    else:
        print(f"  Payload     : {json.dumps(block.data)}")
        
    print(f"  Merkle Root : {block.merkle_root}")
    print(f"  Prev Hash   : {block.previous_hash}")
    print(f"  Mined Hash  : {block.hash}")
    print(f"  Nonce       : {block.nonce:,}")
    if attempts is not None and elapsed is not None:
        rate = (attempts / elapsed) if elapsed > 0 else float("inf")
        print(f"  Mining Stats: {attempts:,} attempts in {elapsed:.4f}s ({rate:,.0f} H/s)")
    print(sep + "\n")


def main() -> None:
    """
    Demonstrates blockchain creation, mining, validation,
    direct tampering detection, cascading cryptographic breakdown,
    and advanced mempool balance verification.
    """
    banner = "=" * 74
    print("\n" + banner)
    print("      INDUSTRIAL TRAINING KIT: PROJECT 1 - MINI-BLOCKCHAIN DEMO      ")
    print(banner + "\n")

    # 1. Chain Initialization
    difficulty = 4
    print(f"[*] Initializing Blockchain with Proof-of-Work Difficulty = {difficulty} ('0' * {difficulty})")
    print("[*] Mining Genesis Block (Index 0)...")
    chain = Blockchain(difficulty=difficulty)
    genesis = chain.chain[0]
    print_block_summary(genesis)

    # 2. Mine Sample Transaction Blocks
    sample_transactions = [
        {"sender": "Alice", "receiver": "Bob", "amount": 50.0},
        {"sender": "Bob", "receiver": "Charlie", "amount": 25.5},
        {"sender": "Charlie", "receiver": "Dave", "amount": 10.0},
    ]

    print("[*] Mining 3 Blocks with Sample Transaction Payloads...\n")
    for tx in sample_transactions:
        block, attempts, elapsed = chain.add_block(tx)
        print_block_summary(block, attempts=attempts, elapsed=elapsed)

    # 3. Initial Validation
    print("-" * 74)
    print("[PHASE 1] RUNNING INITIAL BLOCKCHAIN INTEGRITY AUDIT")
    print("-" * 74)
    initial_validation = chain.is_chain_valid()
    print(f"is_chain_valid() -> {initial_validation}")
    assert initial_validation.is_valid, "Error: Initial chain should be valid!"

    # 4. Tamper Test (Mutating Data inside Block 1)
    print("\n" + "-" * 74)
    print("[PHASE 2] TAMPER TEST: DIRECT PAYLOAD MUTATION")
    print("-" * 74)
    original_data = chain.chain[1].data
    tampered_data = {"sender": "Alice", "receiver": "Eve", "amount": 1000.0}

    print(f"[*] Modifying Block #1 data directly:")
    print(f"    Original : {original_data}")
    print(f"    Tampered : {tampered_data}")
    chain.chain[1].data = tampered_data

    print("\n[*] Re-running is_chain_valid() on tampered chain:")
    tamper_result = chain.is_chain_valid()
    print(f"is_chain_valid() -> {tamper_result.is_valid}")
    print(f"Failure Diagnosis: {tamper_result.reason}\n")
    print(">> EXPLANATION: Check 1 caught this immediately because the stored hash")
    print("   was computed from the original data. Modifying the data without updating")
    print("   the hash breaks the identity `recomputed_hash == stored_hash`.")

    # 5. Cascading Failure Test (Re-mining Only Block 1)
    print("\n" + "-" * 74)
    print("[PHASE 3] CASCADING FAILURE TEST: RE-MINING THE TAMPERED BLOCK ONLY")
    print("-" * 74)
    print("[*] Attacker re-mines Block #1 to fix its stored hash and satisfy difficulty target...")
    new_hash, attempts, elapsed = chain.mine_block(chain.chain[1])
    print(f"[*] Block #1 re-mined successfully!")
    print(f"    New Nonce : {chain.chain[1].nonce}")
    print(f"    New Hash  : {chain.chain[1].hash} ({attempts:,} attempts in {elapsed:.4f}s)")

    print("\n[*] Re-running is_chain_valid() after re-mining only Block #1:")
    remined_result = chain.is_chain_valid()
    print(f"is_chain_valid() -> {remined_result.is_valid}")
    print(f"Failure Diagnosis: {remined_result.reason}\n")

    print("+" + "-" * 72 + "+")
    print("|                     CASCADING FAILURE EXPLANATION                      |")
    print("+" + "-" * 72 + "+")
    print("| Even though Block 1 now has a valid hash matching its tampered data,   |")
    print("| Block 2's `previous_hash` still references Block 1's OLD hash.         |")
    print("|                                                                        |")
    print("| Because cryptographic hashes are one-way and unique, changing Block 1  |")
    print("| produces a completely different hash. This breaks the link to         |")
    print("| Block 2. To fake history, an attacker would have to re-mine Block 1,   |")
    print("| update Block 2's previous_hash, re-mine Block 2, update Block 3,      |")
    print("| and re-mine EVERY subsequent block in the chain faster than the rest  |")
    print("| of the network!                                                       |")
    print("+" + "-" * 72 + "+")

    # 6. Advanced Feature Demo: Mempool, Coinbase Rewards & Balance Ledger
    print("\n" + "-" * 74)
    print("[PHASE 4] MEMPOOL, MINING REWARD & BALANCE LEDGER DEMO")
    print("-" * 74)
    fresh_chain = Blockchain(difficulty=3, mining_reward=50.0)
    print("[*] Created fresh chain (difficulty=3). Mining Block #1 with miner 'Miner_Sam'...")
    fresh_chain.mine_pending_transactions(miner_address="Miner_Sam")

    print(f"[*] Miner_Sam balance: {fresh_chain.get_balance('Miner_Sam'):.2f} coins (Coinbase Reward)")
    
    print("[*] Sam sends 30 coins to Alice...")
    fresh_chain.add_transaction(sender="Miner_Sam", receiver="Alice", amount=30.0)

    print("[*] Alice attempts to overspend: send 100 coins to Bob...")
    success = fresh_chain.add_transaction(sender="Alice", receiver="Bob", amount=100.0)
    assert not success, "Error: Overspending should be rejected!"

    print("[*] Alice sends valid 15 coins to Bob...")
    fresh_chain.add_transaction(sender="Alice", receiver="Bob", amount=15.0)

    print("[*] Mining pending mempool transactions into Block #2 with miner 'Miner_Sam'...")
    b2, _, _ = fresh_chain.mine_pending_transactions(miner_address="Miner_Sam")
    print_block_summary(b2)

    print(f"[*] Final Confirmed Balances:")
    print(f"    Miner_Sam : {fresh_chain.get_balance('Miner_Sam'):.2f} coins")
    print(f"    Alice     : {fresh_chain.get_balance('Alice'):.2f} coins")
    print(f"    Bob       : {fresh_chain.get_balance('Bob'):.2f} coins")
    print(f"[*] Chain Valid: {fresh_chain.is_chain_valid().is_valid}")

    print("\n" + banner)
    print("                         DEMONSTRATION COMPLETE                         ")
    print(banner + "\n")


if __name__ == "__main__":
    main()
