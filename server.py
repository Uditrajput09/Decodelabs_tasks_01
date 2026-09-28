"""
Mini-Blockchain REST API & Static Server
========================================
A zero-dependency HTTP server built with Python standard library only
(http.server, urllib.parse, json) that bridges mini_blockchain.py to the web frontend.
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

# Ensure local directory is importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from mini_blockchain import Block, Blockchain, compute_merkle_root


class BlockchainServerState:
    """Encapsulates the in-memory blockchain state for the web server."""

    def __init__(self, difficulty: int = 3) -> None:
        self.default_difficulty = difficulty
        self.blockchain = Blockchain(difficulty=difficulty, mining_reward=50.0)
        self.seed_sample_data()

    def seed_sample_data(self) -> None:
        """Pre-seeds realistic blocks so the explorer is informative on first load."""
        # Block 1: Miner awards and setup
        self.blockchain.mine_pending_transactions(miner_address="Miner_Sam")

        # Block 2: Transfers
        self.blockchain.add_transaction(sender="Miner_Sam", receiver="Alice", amount=30.0)
        self.blockchain.mine_pending_transactions(miner_address="Miner_Sam")

        # Block 3: Alice sends to Bob
        self.blockchain.add_transaction(sender="Alice", receiver="Bob", amount=12.5)
        self.blockchain.mine_pending_transactions(miner_address="Miner_Sam")

    def reset(self) -> None:
        """Re-initializes the blockchain back to fresh initial state."""
        self.blockchain = Blockchain(difficulty=self.default_difficulty, mining_reward=50.0)
        self.seed_sample_data()

    def get_tracked_balances(self) -> Dict[str, float]:
        """Returns spendable balances for common demo accounts."""
        accounts = ["Miner_Sam", "Alice", "Bob", "Charlie", "Dave", "Eve"]
        return {acc: self.blockchain.get_balance(acc, include_pending=True) for acc in accounts}

    def serialize_state(self) -> Dict[str, Any]:
        """Produces a JSON-serializable snapshot of the blockchain."""
        validation = self.blockchain.is_chain_valid()
        return {
            "difficulty": self.blockchain.difficulty,
            "mining_reward": self.blockchain.mining_reward,
            "chain_length": len(self.blockchain.chain),
            "is_valid": validation.is_valid,
            "validation_reason": validation.reason,
            "balances": self.get_tracked_balances(),
            "pending_transactions": self.blockchain.pending_transactions,
            "chain": [
                {
                    "index": b.index,
                    "timestamp": b.timestamp,
                    "data": b.data,
                    "previous_hash": b.previous_hash,
                    "nonce": b.nonce,
                    "hash": b.hash,
                    "merkle_root": b.merkle_root,
                    "recomputed_hash": b.compute_hash(),
                    "is_stored_hash_valid": b.compute_hash() == b.hash,
                    "is_link_valid": (
                        b.previous_hash == "0"
                        if b.index == 0
                        else b.previous_hash == self.blockchain.chain[b.index - 1].hash
                    ),
                    "meets_target": b.hash.startswith("0" * self.blockchain.difficulty),
                }
                for b in self.blockchain.chain
            ],
        }


# Global server state instance
SERVER_STATE = BlockchainServerState(difficulty=3)


class BlockchainAPIHandler(SimpleHTTPRequestHandler):
    """Handles REST API requests and serves static web assets."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=CURRENT_DIR, **kwargs)

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Helper to send JSON response with CORS headers."""
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        """Route GET requests: APIs or static web files."""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/chain":
            self._send_json(SERVER_STATE.serialize_state())
        elif path == "/api/validate":
            result = SERVER_STATE.blockchain.is_chain_valid()
            self._send_json({"is_valid": result.is_valid, "reason": result.reason})
        elif path in ["", "/"]:
            self.path = "/index.html"
            super().do_GET()
        else:
            # Fall back to serving static files (index.html, style.css, app.js)
            super().do_GET()

    def do_POST(self) -> None:
        """Route POST requests for mutating actions."""
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON payload"}, 400)
            return

        bc = SERVER_STATE.blockchain

        if path == "/api/transaction":
            sender = params.get("sender", "").strip()
            receiver = params.get("receiver", "").strip()
            try:
                amount = float(params.get("amount", 0.0))
            except ValueError:
                self._send_json({"error": "Amount must be a numeric value"}, 400)
                return

            if not sender or not receiver:
                self._send_json({"error": "Sender and receiver are required"}, 400)
                return

            success = bc.add_transaction(sender=sender, receiver=receiver, amount=amount)
            if success:
                self._send_json({
                    "success": True,
                    "message": f"Queued {amount:.2f} coins from {sender} to {receiver}",
                    "state": SERVER_STATE.serialize_state(),
                })
            else:
                current_bal = bc.get_balance(sender, include_pending=True)
                self._send_json({
                    "success": False,
                    "error": f"Insufficient balance for {sender}. Available: {current_bal:.2f}",
                }, 400)

        elif path == "/api/mine":
            miner = params.get("miner_address", "Miner_Sam").strip() or "Miner_Sam"
            new_diff = params.get("difficulty")
            if new_diff is not None:
                bc.difficulty = max(1, min(5, int(new_diff)))

            block, attempts, elapsed = bc.mine_pending_transactions(miner_address=miner)
            self._send_json({
                "success": True,
                "block": block.to_dict(),
                "attempts": attempts,
                "elapsed": elapsed,
                "state": SERVER_STATE.serialize_state(),
            })

        elif path == "/api/tamper":
            try:
                block_index = int(params.get("index", -1))
            except ValueError:
                self._send_json({"error": "Index must be an integer"}, 400)
                return

            if block_index < 0 or block_index >= len(bc.chain):
                self._send_json({"error": f"Invalid block index {block_index}"}, 400)
                return

            new_data = params.get("data")
            if new_data is None:
                self._send_json({"error": "New data is required"}, 400)
                return

            # Mutate block data directly without re-mining
            bc.chain[block_index].data = new_data
            self._send_json({
                "success": True,
                "message": f"Block #{block_index} data modified directly.",
                "state": SERVER_STATE.serialize_state(),
            })

        elif path == "/api/remine":
            try:
                block_index = int(params.get("index", -1))
            except ValueError:
                self._send_json({"error": "Index must be an integer"}, 400)
                return

            if block_index < 0 or block_index >= len(bc.chain):
                self._send_json({"error": f"Invalid block index {block_index}"}, 400)
                return

            # Re-mine ONLY that block
            target_block = bc.chain[block_index]
            new_hash, attempts, elapsed = bc.mine_block(target_block)

            self._send_json({
                "success": True,
                "message": f"Block #{block_index} re-mined (hash: {new_hash[:10]}...).",
                "attempts": attempts,
                "elapsed": elapsed,
                "state": SERVER_STATE.serialize_state(),
            })

        elif path == "/api/repair":
            # Re-mine from a given index all the way to the end of the chain
            try:
                start_index = int(params.get("index", 1))
            except ValueError:
                start_index = 1

            total_attempts = 0
            start_time = time.time()

            for i in range(max(1, start_index), len(bc.chain)):
                current = bc.chain[i]
                prev = bc.chain[i - 1]
                # Fix previous_hash linkage
                current.previous_hash = prev.hash
                # Re-mine current block
                _, attempts, _ = bc.mine_block(current)
                total_attempts += attempts

            elapsed_total = time.time() - start_time
            self._send_json({
                "success": True,
                "message": f"Repaired chain from Block #{start_index} to #{len(bc.chain)-1}.",
                "total_attempts": total_attempts,
                "elapsed": elapsed_total,
                "state": SERVER_STATE.serialize_state(),
            })

        elif path == "/api/difficulty":
            try:
                diff = int(params.get("difficulty", 3))
                bc.difficulty = max(1, min(5, diff))
                self._send_json({
                    "success": True,
                    "difficulty": bc.difficulty,
                    "state": SERVER_STATE.serialize_state(),
                })
            except ValueError:
                self._send_json({"error": "Difficulty must be integer 1..5"}, 400)

        elif path == "/api/reset":
            SERVER_STATE.reset()
            self._send_json({
                "success": True,
                "message": "Blockchain reset to initial state.",
                "state": SERVER_STATE.serialize_state(),
            })

        else:
            self._send_json({"error": f"Unknown endpoint {path}"}, 404)


def run_server(port: int = 8000) -> None:
    """Starts the Python HTTP and REST API server."""
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, BlockchainAPIHandler)
    print(f"\n=======================================================")
    print(f" Mini-Blockchain Explorer & PoW Studio Running at:")
    print(f" http://localhost:{port} (or http://127.0.0.1:{port})")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)
