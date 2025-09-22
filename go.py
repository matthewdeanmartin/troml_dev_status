import glob
import os
from pathlib import Path

import troml_dev_status


def run():
    os.environ["TROML_DEV_STATUS_VENV_MODE"]  ="1"
    for file in glob.glob("./.venv/Lib/site-packages/*"):
        path = Path(file)
        if path.is_dir():
            if ".dist-info" in path.name:
                continue
            print(path)
            er = troml_dev_status.run_analysis(path, project_name=path.name)
            print(er)

if __name__ == '__main__':
    run()