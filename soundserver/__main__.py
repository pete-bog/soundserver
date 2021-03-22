import logging

from soundserver.main import main

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

if __name__ == "__main__":
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
    main()
