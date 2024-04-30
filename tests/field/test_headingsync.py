import pytest
from pysagax.field.ppheadingsync import PPHeadingSync
import pysagax.message.heading_pb2 as proto_heading
from queue import Queue


def create_heading_sync(initial_deque, target_time) -> PPHeadingSync:
    """
    Creating and PPHeadingSync object that has a heading_deque defined by the timestamps in initial_deque
    Params:
        initial_deque: timestamps of packets. The heading_deque is created based on this
            If its None then the deque remains in its orignal state
        target_time: delta_t-s are calculated based on this value
    """

    hs = PPHeadingSync()

    # Modifying the deque if an initial_deque passed
    if initial_deque is None:
        pass
    elif len(initial_deque) == 1:
        new = {"delta_t": float("inf"), "data": proto_heading.HeadingData()}
        new["delta_t"] = abs(initial_deque[0] - target_time)
        new["data"].timestamp.FromNanoseconds(initial_deque[0])
        hs.heading_deque.append(new)
    elif len(initial_deque) == 2:
        old = {"delta_t": float("inf"), "data": proto_heading.HeadingData()}
        new = {"delta_t": float("inf"), "data": proto_heading.HeadingData()}

        old["delta_t"] = abs(initial_deque[0] - target_time)
        old["data"].timestamp.FromNanoseconds(initial_deque[0])

        new["delta_t"] = abs(initial_deque[1] - target_time)
        new["data"].timestamp.FromNanoseconds(initial_deque[1])

        hs.heading_deque.append(old)
        hs.heading_deque.append(new)
    else:
        pytest.fail("Initial dequeue can be None or have a length of 1 or 2")

    return hs


@pytest.mark.parametrize(
    ["initial_deque", "heading_t", "target_time", "expected_t", "final_deque"],
    [
        # long heading queue with the correct best fit in various places
        [None, [1, 2, 3, 4, 5], 3.2, 3, [3, 4]],
        [None, [3, 4, 5, 6, 7], 3.2, 3, [3, 4]],
        [None, [3, 4, 5, 6, 7], 1.2, 3, [3, 4]],
        [None, [1, 2, 3, 4, 5], 4.2, 4, [4, 5]],
        [None, [1, 2, 3, 4, 5], 4.9, 5, [4, 5]],
        [None, [1, 2, 3, 4, 5], 5.2, 5, [4, 5]],
        [None, [1, 2, 3, 4, 5], 10.2, 5, [4, 5]],
        # same values in queue:
        [None, [1, 2, 3, 3, 3, 3, 4, 5], 3.2, 3, [3, 4]],
        [None, [1, 2, 3, 3, 3, 3, 4, 5], 3, 3, [3, 4]],
        [None, [1, 2, 3, 3, 3, 3, 4, 5], 2.8, 3, [3, 4]],
        [None, [1, 2, 3, 3, 3, 3, 4, 5], 4.8, 5, [4, 5]],
        # same time differences from the target_time:
        [None, [1, 2, 3, 5, 6], 4, 5, [5, 6]],
        # initial state is not empty:
        [[1], [3, 4, 5, 6, 7], 3.2, 3, [3, 4]],  #
        [[1], [3, 4, 5, 6, 7], 1.2, 1, [1, 3]],  #
        [[1, 2], [5, 6], 1.8, 2, [2, 5]],
        [[1, 2], [5, 6], 3.2, 2, [2, 5]],
        [[1, 2], [5, 6], 4.2, 5, [5, 6]],
        [[1, 2], [5, 6], 1.2, 1, [1, 2]],
        # empty heading queue:
        [[1, 2], [], 3.2, 2, [1, 2]],
        [[1, 2], [], 1.2, 1, [1, 2]],
        [[1], [], 3.2, 1, [0, 1]],
        [[1], [], 0.2, 1, [0, 1]],
        [None, [], 3.2, 0, [0, 0]],
        # wrong order, shouldn't happen while running
        [None, [5, 4, 3, 2, 1], 3.2, 3, [3, 2]],
        [None, [5, 4, 1, 3, 2], 3.2, 4, [4, 1]],
    ],
)
def test_best_fit(initial_deque, heading_t, target_time, expected_t, final_deque):
    """
    Testing heading sync's best fit finding function
    Parameters:
        initial_deque: optional list of timestamps for heading_packets already in the deque
        heading_t: list of heading packet timestamps for packets in the heading_queue_in
        target_time: a timestamp for which the best fitting heading should be found
        expected_t: timestamp of the best fitting heading packet
        final_deque: timestamps describing the state of the heading_deque after the test ran
    """
    hs = create_heading_sync(initial_deque, target_time)

    # create heading packet queue
    hs._heading_queue_in = Queue()
    for t in heading_t:
        h_packet = proto_heading.HeadingData()
        h_packet.timestamp.FromNanoseconds(t)
        hs._heading_queue_in.put(h_packet)
        print(h_packet)

    best_delta_t, best_fit = hs._get_best_fitting_heading(target_time)
    print(hs.heading_deque)
    print("Best delta_t", best_delta_t, "best_fit", best_fit)

    # test for correctly chosen packet
    assert best_fit.timestamp.ToNanoseconds() == expected_t

    # test for leaving the heading deque in an expected state
    assert hs.heading_deque[0]["data"].timestamp.ToNanoseconds() == final_deque[0]
    assert hs.heading_deque[1]["data"].timestamp.ToNanoseconds() == final_deque[1]
    if final_deque[0] == 0:
        # protobuf timestamp default value is 0, whereas the default delta_t in sync is +inf
        assert hs.heading_deque[0]["delta_t"] == float("inf")
    else:
        assert hs.heading_deque[0]["delta_t"] == abs(final_deque[0] - target_time)
    if final_deque[1] == 0:
        assert hs.heading_deque[1]["delta_t"] == float("inf")
    else:
        assert hs.heading_deque[1]["delta_t"] == abs(final_deque[1] - target_time)


@pytest.mark.parametrize(
    ["initial_deque", "target_time", "expected_delta_t"],
    [
        # freshly initialized deque
        [None, 3.2, [float("inf"), float("inf")]],
        [None, -3.2, [float("inf"), float("inf")]],
        [None, 0, [float("inf"), float("inf")]],
        # # initial state is not empty:
        [[1], 2, [float("inf"), 1]],
        [[1], 1, [float("inf"), 0]],
        [[1], -1, [float("inf"), 2]],
        [[1, 2], 3, [2, 1]],
        [[1, 2], 2, [1, 0]],
        [[1, 2], 1.5, [0.5, 0.5]],
        [[1, 2], 1, [0, 1]],
        [[1, 2], 0, [1, 2]],
    ],
)
def test_update_delta_t(initial_deque, target_time, expected_delta_t):
    """
    Test PPHeadingSync._update_delta_t()
    Params:
        initial deque: list of heading packet timestamps before running _update_delta_t
        target_time: timestamp to compare the deque with
        expected_delta_t: list of absolute time differences (not timestamps!)
    """
    # dont pass the corrct target_time for initialization
    hs = create_heading_sync(initial_deque, -123)

    hs._update_delta_t(target_time)
    assert hs.heading_deque[0]["delta_t"] == expected_delta_t[0]
    assert hs.heading_deque[1]["delta_t"] == expected_delta_t[1]
