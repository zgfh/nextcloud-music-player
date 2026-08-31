"""DownloadProgressTracker：按文件维护的下载列表状态机与聚合快照"""

from nextcloud_music_player.services.download_progress import DownloadProgressTracker


def test_lifecycle_states_in_queue_order():
    tracker = DownloadProgressTracker()
    tracker.enqueue(["a.mp3", "b.mp3", "c.mp3"])
    tracker.mark_downloading("a.mp3")
    tracker.update("a.mp3", 50, 100)
    tracker.finish("a.mp3", True)
    tracker.finish("b.mp3", False, "boom")

    states = tracker.file_states()
    assert [s["filename"] for s in states] == ["a.mp3", "b.mp3", "c.mp3"]
    assert [s["status"] for s in states] == ["completed", "failed", "queued"]
    # 完成后进度补齐到总量
    assert states[0]["downloaded_bytes"] == 100
    assert states[0]["total_bytes"] == 100

    snapshot = tracker.snapshot()
    assert snapshot["completed"] == 1
    assert snapshot["failed"] == 1
    assert snapshot["queued"] == 1
    # 仍有排队项时聚合状态为 queued
    assert snapshot["status"] == "queued"


def test_empty_tracker_is_idle():
    tracker = DownloadProgressTracker()
    assert tracker.snapshot()["status"] == "idle"
    assert tracker.file_states() == []


def test_enqueue_deduplicates_and_requeues_finished():
    tracker = DownloadProgressTracker()
    assert tracker.enqueue(["a.mp3", "a.mp3"]) == 1  # 排队中重复入队只保留一条
    tracker.mark_downloading("a.mp3")
    tracker.finish("a.mp3", True)

    assert tracker.enqueue("a.mp3") == 1  # 完成后重新入队会重置
    assert tracker.file_states()[0]["status"] == "queued"


def test_progress_on_queued_file_promotes_to_downloading():
    """原生任务的进度可能先于标记到达：就地激活而不是丢弃"""
    tracker = DownloadProgressTracker()
    tracker.enqueue("a.mp3")
    tracker.update("a.mp3", 10, 100)

    state = tracker.file_states()[0]
    assert state["status"] == "downloading"
    assert state["downloaded_bytes"] == 10


def test_mixed_terminal_results_are_partial():
    tracker = DownloadProgressTracker()
    tracker.enqueue(["a.mp3", "b.mp3"])
    tracker.finish("a.mp3", True)
    tracker.finish("b.mp3", False, "HTTP 404")

    snapshot = tracker.snapshot()
    assert snapshot["status"] == "partial"
    assert snapshot["completed"] == 1
    assert snapshot["failed"] == 1
    assert snapshot["message"] == "HTTP 404"


def test_aggregate_bytes_and_speed():
    tracker = DownloadProgressTracker()
    tracker.enqueue(["a.mp3", "b.mp3"])
    tracker.mark_downloading("a.mp3")
    tracker.mark_downloading("b.mp3")
    tracker.update("a.mp3", 100, 200)
    tracker.update("b.mp3", 50, 300)

    snapshot = tracker.snapshot()
    assert snapshot["downloading"] == 2
    assert snapshot["downloaded_bytes"] == 150
    assert snapshot["total_bytes"] == 500
    assert snapshot["speed_bps"] > 0
