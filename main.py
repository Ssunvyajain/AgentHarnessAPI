from fastapi import FastAPI
from pydantic import BaseModel
import json
import re


app = FastAPI()


class RunRequest(BaseModel):
    budget_tokens: int
    steps: list


def normalize(value):
    """
    Normalize arguments:
    - remove trace_id
    - ignore key order
    - remove whitespace differences
    """

    if isinstance(value, dict):

        result = {}

        for k, v in sorted(value.items()):

            if k == "trace_id":
                continue

            result[k] = normalize(v)

        return result


    elif isinstance(value, list):

        return [normalize(x) for x in value]


    elif isinstance(value, str):

        return re.sub(r"\s+", " ", value).strip()


    else:
        return value



def step_signature(step):

    return (
        step.get("tool"),
        json.dumps(
            normalize(step.get("args", {})),
            sort_keys=True
        )
    )



def check_three_repeat(steps):

    if len(steps) < 3:
        return False


    last_three = steps[-3:]

    signatures = [
        step_signature(x)
        for x in last_three
    ]

    return len(set(signatures)) == 1



def check_ab_cycle(steps):

    if len(steps) < 6:
        return False


    last = steps[-6:]

    sig = [
        step_signature(x)
        for x in last
    ]


    return (
        sig[0] == sig[2] == sig[4]
        and
        sig[1] == sig[3] == sig[5]
        and
        sig[0] != sig[1]
    )



@app.get("/")
def root():

    return {
        "message":"Agent Harness API running"
    }



@app.post("/check")
def check(req: RunRequest):

    steps = req.steps


    # ----------------------
    # TOKEN CHECK
    # ----------------------

    total_tokens = sum(
        step.get("tokens_used",0)
        for step in steps
    )


    if total_tokens >= req.budget_tokens:

        return {
            "decision":"halt",
            "reason":
            f"Cumulative tokens_used ({total_tokens}) has reached the budget ({req.budget_tokens})."
        }



    # ----------------------
    # LOOP CHECK
    # ----------------------

    if check_three_repeat(steps):

        return {
            "decision":"halt",
            "reason":
            "Repeated identical tool call detected three times in a row."
        }



    if check_ab_cycle(steps):

        return {
            "decision":"halt",
            "reason":
            "Repeating two-step tool cycle detected."
        }



    return {
        "decision":"continue",
        "reason":
        f"Under budget ({total_tokens}/{req.budget_tokens}) and no loop detected."
    }