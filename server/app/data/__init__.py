from app.db import name_col
import os
import json
import pandas as pd
import asyncio
from concurrent.futures import ThreadPoolExecutor


name_dict = None
_executor = ThreadPoolExecutor(max_workers=1)


def _load_name_dict_sync():
    if os.getenv("LLM_NAME_SOURCE") == "local":
        with open(
            os.path.join(os.path.dirname(__file__), "llm_names.json"),
            encoding="utf-8",
        ) as f:
            data = json.load(f)
        return {d["name"]: d["score"] for d in data}

    print("Loading LLM names from DB")
    docs = list(
        name_col.find({}, {"_id": 0, "name": 1, "score": 1})
    )
    result = {d["name"]: d["score"] for d in docs}
    print(f"Loaded {len(result)} LLM names from DB")
    return result


async def load_name_dict():
    global name_dict
    if name_dict is not None:
        return name_dict

    loop = asyncio.get_running_loop()
    name_dict = await loop.run_in_executor(
        _executor, _load_name_dict_sync
    )
    return name_dict


def get_name_dict():
    if name_dict is None:
        raise RuntimeError("name_dict not initialized")
    return name_dict


conf_df = pd.read_csv(
    os.path.join(os.path.dirname(__file__), "conf.csv")
)
conf_param_list = conf_df["param"].tolist()
conf_param_dict = conf_df.set_index("conference")["param"].to_dict()
param_conf_dict = conf_df.set_index("param")["conference"].to_dict()


def get_conferences_for_ui():
    cols = ["kind", "conference"]
    missing = [c for c in cols if c not in conf_df.columns]
    if missing:
        raise RuntimeError(f"conf.csv missing columns: {missing}")
    return conf_df[cols].to_dict(orient="records")
