import json

from backend.app.ml.train import diagnose


if __name__ == "__main__":
    print(json.dumps(diagnose(), indent=2, default=str))

