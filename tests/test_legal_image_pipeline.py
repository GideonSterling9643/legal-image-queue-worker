import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from legal_image_pipeline import MatterImage, resize_plan


def test_signed_documents_get_the_review_width():
    item = MatterImage("matter-1", "order.jpg", "image-1", True, 30)
    assert resize_plan(item) == (1600, 1200)


def test_deadline_follow_up_uses_larger_intake_target():
    item = MatterImage("matter-2", "notice.jpg", "image-2", False, 5)
    assert resize_plan(item) == (1200, 900)
