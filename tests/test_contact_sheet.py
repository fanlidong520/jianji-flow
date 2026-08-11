from jianji_flow.contact_sheet import build_frame_times_ms


def test_build_frame_times_ms_spreads_frames_across_duration():
    assert build_frame_times_ms(10_000, frames=5) == [1000, 3000, 5000, 7000, 9000]
