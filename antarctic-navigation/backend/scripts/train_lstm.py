"""Train the LSTM iceberg trajectory model on the loaded BYU tracks."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.pipeline import ensure_loaded
from app.ml.iceberg_trajectory import evaluate_split

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train")

def main():
    logger.info("Loading tracks via pipeline...")
    state = ensure_loaded(include_sar=False)
    tracks = state.get("tracks", [])
    
    if not tracks:
        logger.error("No tracks loaded. Make sure the dataset is available.")
        return
        
    logger.info(f"Loaded {len(tracks)} tracks. Starting training...")
    metrics = evaluate_split(tracks, holdout_frac=0.15, seed=42)
    logger.info("Training complete.")
    logger.info(metrics)

if __name__ == "__main__":
    main()
