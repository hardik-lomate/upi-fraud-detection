"""Backend training entrypoint.

Invokes the shared ML training pipeline used for bank-side fraud models.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from ml.train_model import main


if __name__ == "__main__":
    main()
