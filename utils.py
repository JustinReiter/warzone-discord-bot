from datetime import datetime
import json
import traceback

import jsonpickle


def read_pickled_file(file_name):
    with open(file_name, "r", encoding="utf-8") as file:
        return jsonpickle.decode(json.load(file))


def write_pickled_file(file_name, data):
    with open(file_name, "w", encoding="utf-8") as file:
        json.dump(jsonpickle.encode(data), file)


def log_message(msg: str, type="FIXME"):
    output_msg = f"[{datetime.now().isoformat()}] {type}: {msg.encode()}"
    print(output_msg)
    with open(
        "./logs/{}.txt".format(datetime.now().isoformat()[:10]), "a"
    ) as log_writer:
        log_writer.write(f"{output_msg}\n")


def log_exception(msg: Exception | str):
    time_str = "[" + datetime.now().isoformat() + "] {}: ".format(type)
    print("{}{}\n{}\n".format(time_str, repr(msg).encode(), traceback.format_exc()))
    with open(
        "./logs/{}.txt".format(datetime.now().isoformat()[:10]), "a"
    ) as log_writer:
        log_writer.write("{}{}\n".format(time_str, repr(msg).encode()))
    with open(
        "./errors/{}.txt".format(datetime.now().isoformat()[:10]), "a"
    ) as log_writer:
        log_writer.write(
            "{}{}\n{}\n".format(time_str, repr(msg).encode(), traceback.format_exc())
        )
