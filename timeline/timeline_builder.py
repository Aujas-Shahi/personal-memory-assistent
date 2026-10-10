import os
from datetime import datetime

from config.settings import FILES_DIR as DATA_FOLDER


def build_timeline():
    items = []

    if not os.path.exists(DATA_FOLDER):
        return {"items": items}

    for file_name in os.listdir(DATA_FOLDER):

        file_path = os.path.join(DATA_FOLDER, file_name)

        if os.path.isfile(file_path):

            timestamp = datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).strftime("%Y-%m-%d %H:%M:%S")

            items.append({
                "file_name": file_name,
                "timestamp": timestamp
            })

    return {"items": items}