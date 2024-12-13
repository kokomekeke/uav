import json
import pysagax.message.command_pb2 as proto_cmd


def roi_mask_from_json(path: str):
    """
    Parses a roi config json file.
    The file should contain a "roi_mask" array that has objects
    with "center_frequency", "span", "threshold" and optionally "roi_id" fields
    """
    file = open(path)
    mask_json = json.load(file)

    defined_roi_ids = [
        roi_j["roi_id"] for roi_j in mask_json["roi_mask"] if "roi_id" in roi_j.keys()
    ]
    smallest_free_roi_id = 1 + min(defined_roi_ids) if len(defined_roi_ids) else 0

    roi_mask: list[proto_cmd.ROIMask] = []
    for roi_j in mask_json["roi_mask"]:
        roi = proto_cmd.ROIMask(
            center_frequency=roi_j["center_frequency"],
            span=roi_j["span"],
            threshold=roi_j["threshold"],
        )
        if "roi_id" in roi_j:
            roi.roi_id = roi_j["roi_id"]
        else:
            roi.roi_id = smallest_free_roi_id
            smallest_free_roi_id += 1
        roi_mask.append(roi)
    return roi_mask
