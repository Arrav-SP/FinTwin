import json

from backend.app.ml.train import train_models


if __name__ == "__main__":
    print(json.dumps(train_models(), indent=2, default=str))

