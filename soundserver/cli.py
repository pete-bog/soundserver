import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--store',
                        help='Path to the directory to store sounds',
                        required=True)
    parser.add_argument('--host', default="0.0.0.0", help='Host address')
    parser.add_argument('--port', default=8000, help='Listen on port')
    parser.add_argument('--dev-mode',
                        action="store_true",
                        help='Run in development mode')
    args = parser.parse_args()
    return args