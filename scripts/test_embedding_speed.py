#!/usr/bin/env python3
"""Test embedding generation speed with different batch sizes"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import torch
from sentence_transformers import SentenceTransformer


def test_embedding_speed():
    """Test embedding speed with GPU"""
    print("=" * 60)
    print("EMBEDDING SPEED TEST")
    print("=" * 60)

    # Check GPU
    if torch.cuda.is_available():
        device = "cuda"
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"\nGPU: {gpu_name}")
        print(f"Memory: {gpu_memory:.1f} GB")
    else:
        device = "cpu"
        print("\nDevice: CPU (no GPU detected)")

    # Load model
    print("\nLoading BGE-base-en-v1.5 model...")
    model = SentenceTransformer("BAAI/bge-base-en-v1.5", device=device)
    print("Model loaded")

    # Test data
    test_chunks = [
        "This is a test patent claim about a novel invention." * 10
    ] * 1000  # 1000 chunks for testing

    print(f"\nTest data: {len(test_chunks):,} chunks")
    print(f"Avg length: {len(test_chunks[0])} chars")

    # Test different batch sizes
    batch_sizes = [32, 64, 128, 256, 512] if device == "cuda" else [16, 32, 64]

    measurements = []

    for batch_size in batch_sizes:
        print(f"\n{'='*60}")
        print(f"Testing batch_size={batch_size}")
        print("=" * 60)

        try:
            start = time.time()
            embeddings = model.encode(
                test_chunks,
                batch_size=batch_size,
                show_progress_bar=True,
                device=device,
            )
            elapsed = time.time() - start

            speed = len(test_chunks) / elapsed
            measurements.append((speed, batch_size))
            print(f"\n[OK] Completed in {elapsed:.2f} seconds")
            print(f"  Speed: {speed:.0f} chunks/sec")
            print(f"  Generated: {len(embeddings):,} embeddings")

        except Exception as e:
            print(f"\n[X] Failed: {e}")

    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    if not measurements:
        print("No batch size completed successfully. No recommendation is available.")
        return 1
    speed, batch_size = max(measurements)
    print(f"Use batch_size={batch_size} (fastest successful batch in this run)")
    print(f"Measured {speed:.0f} chunks/sec on {device}")
    return 0


if __name__ == "__main__":
    sys.exit(test_embedding_speed())
