"""
Unit Test Suite for Mini-Blockchain
===================================
Tests core blockchain functionality, Proof-of-Work, Merkle tree hashing,
dual-phase integrity auditing, and mempool balance verification.
"""

import unittest
from mini_blockchain import Block, Blockchain, compute_merkle_root


class TestMiniBlockchain(unittest.TestCase):
    """Test cases for the mini-blockchain implementation."""

    def setUp(self) -> None:
        """Initialize a fresh low-difficulty blockchain for rapid testing."""
        self.difficulty = 2
        self.chain = Blockchain(difficulty=self.difficulty, mining_reward=50.0)

    def test_genesis_block(self) -> None:
        """Verify Genesis block is properly initialized and mined."""
        self.assertEqual(len(self.chain.chain), 1)
        genesis = self.chain.chain[0]
        self.assertEqual(genesis.index, 0)
        self.assertEqual(genesis.previous_hash, "0")
        self.assertEqual(genesis.data, "Genesis Block")
        self.assertTrue(genesis.hash.startswith("0" * self.difficulty))
        self.assertEqual(genesis.compute_hash(), genesis.hash)

    def test_add_block_linkage(self) -> None:
        """Verify adding blocks establishes unbroken cryptographic linkage."""
        block1, attempts, elapsed = self.chain.add_block({"sender": "A", "receiver": "B", "amount": 10.0})
        self.assertEqual(len(self.chain.chain), 2)
        self.assertEqual(block1.index, 1)
        self.assertEqual(block1.previous_hash, self.chain.chain[0].hash)
        self.assertTrue(block1.hash.startswith("0" * self.difficulty))
        self.assertTrue(self.chain.is_chain_valid().is_valid)

    def test_proof_of_work_difficulty(self) -> None:
        """Verify all blocks satisfy the difficulty requirement."""
        self.chain.add_block("Tx 1")
        self.chain.add_block("Tx 2")
        target = "0" * self.difficulty
        for block in self.chain.chain:
            self.assertTrue(block.hash.startswith(target))

    def test_check_1_stored_hash_tampering(self) -> None:
        """Verify Check 1 catches in-place payload alteration."""
        self.chain.add_block({"sender": "Alice", "receiver": "Bob", "amount": 50.0})
        self.chain.add_block({"sender": "Bob", "receiver": "Charlie", "amount": 25.0})

        # Mutate block 1 data directly
        self.chain.chain[1].data = {"sender": "Alice", "receiver": "Eve", "amount": 1000.0}

        validation = self.chain.is_chain_valid()
        self.assertFalse(validation.is_valid)
        self.assertIn("Check 1 Failed", validation.reason)
        self.assertIn("Block 1", validation.reason)

    def test_check_2_cascading_failure(self) -> None:
        """Verify Check 2 catches broken linkage when a past block is re-mined."""
        self.chain.add_block({"sender": "Alice", "receiver": "Bob", "amount": 50.0})
        self.chain.add_block({"sender": "Bob", "receiver": "Charlie", "amount": 25.0})

        # Mutate Block 1 and re-mine it
        self.chain.chain[1].data = {"sender": "Alice", "receiver": "Eve", "amount": 1000.0}
        self.chain.mine_block(self.chain.chain[1])

        # Block 1 now passes Check 1, but Block 2's previous_hash is now invalid
        validation = self.chain.is_chain_valid()
        self.assertFalse(validation.is_valid)
        self.assertIn("Check 2 Failed", validation.reason)
        self.assertIn("Block 2", validation.reason)

    def test_merkle_root_calculation(self) -> None:
        """Verify Merkle root deterministic computation and avalanche behavior."""
        txs = [
            {"sender": "Alice", "receiver": "Bob", "amount": 10},
            {"sender": "Bob", "receiver": "Charlie", "amount": 20},
            {"sender": "Charlie", "receiver": "Dave", "amount": 30},
        ]
        root1 = compute_merkle_root(txs)
        root2 = compute_merkle_root(txs)
        self.assertEqual(root1, root2)

        # Altering 1 transaction completely changes the Merkle root
        txs_tampered = [
            {"sender": "Alice", "receiver": "Bob", "amount": 10.01},  # small edit
            {"sender": "Bob", "receiver": "Charlie", "amount": 20},
            {"sender": "Charlie", "receiver": "Dave", "amount": 30},
        ]
        root_tampered = compute_merkle_root(txs_tampered)
        self.assertNotEqual(root1, root_tampered)

    def test_mempool_coinbase_and_balance_tracking(self) -> None:
        """Verify coinbase mining rewards, mempool queuing, and balance checks."""
        # Miner mines block 1 and receives 50 coinbase reward
        self.chain.mine_pending_transactions(miner_address="Miner")
        self.assertEqual(self.chain.get_balance("Miner"), 50.0)

        # Miner transfers 30 to Alice
        self.assertTrue(self.chain.add_transaction(sender="Miner", receiver="Alice", amount=30.0))

        # Alice tries to overspend (she has 30, requests 40)
        self.assertFalse(self.chain.add_transaction(sender="Alice", receiver="Bob", amount=40.0))

        # Alice transfers valid 20 to Bob
        self.assertTrue(self.chain.add_transaction(sender="Alice", receiver="Bob", amount=20.0))

        # Mine block 2
        self.chain.mine_pending_transactions(miner_address="Miner")

        # Check balances:
        # Miner: 50 (block 1) + 50 (block 2) - 30 (sent to Alice) = 70
        # Alice: 30 (received) - 20 (sent to Bob) = 10
        # Bob: 20 (received) = 20
        self.assertEqual(self.chain.get_balance("Miner"), 70.0)
        self.assertEqual(self.chain.get_balance("Alice"), 10.0)
        self.assertEqual(self.chain.get_balance("Bob"), 20.0)
        self.assertTrue(self.chain.is_chain_valid().is_valid)


if __name__ == "__main__":
    unittest.main()
