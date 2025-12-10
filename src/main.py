#!/usr/bin/env python3
"""
ECU PTS - Performance Testing Software
Entry point for the application.
"""

import sys
import logging
from ecu_pts import main

if __name__ == "__main__":
    # Configure basic logging at the entry point
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    try:
        main()
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
